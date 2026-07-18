#!/usr/bin/env python3
"""Simulation-first V&V campaign for the SMPT manuscript.

This program implements:
  * a nearest-neighbour CTMC discretization of the reflected diffusion surrogate;
  * an independent event-driven compound-jump simulator with exact service-flow decay;
  * threshold optimization, baseline comparisons, and validation metrics;
  * a 36-case factorial design plus a 24-case Latin-hypercube robustness design.

The state is normalized workload pressure, not literal physical KV-block occupancy.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from numba import njit
from scipy import sparse
from scipy.optimize import brentq
from scipy.sparse.linalg import spsolve
from scipy.special import gammaincc
from scipy.stats import qmc, kendalltau, t as student_t

EPS = 1e-12


@dataclass
class Scenario:
    scenario_id: str
    design: str
    K: float
    mu_max: float
    rho: float
    arrival_scv: float
    mean_jump_fraction: float
    tau: float
    qH: float
    beta: float
    jump_cv: float
    cloud_cost_multiplier: float
    deactivation_mean: float
    lambda_H: float
    lambda_L: float
    mean_H: float
    mean_L: float
    cv_H: float
    cv_L: float
    cW: float = 1.0
    cB: float = 10.0
    cL: float = 2.5
    cC: float = 0.25

    @property
    def input_H(self) -> float:
        return self.lambda_H * self.mean_H

    @property
    def input_L(self) -> float:
        return self.lambda_L * self.mean_L

    @property
    def input_total(self) -> float:
        return self.input_H + self.input_L

    @property
    def theta(self) -> float:
        return 1.0 / self.tau

    @property
    def mu_c(self) -> float:
        return 1.0 / self.deactivation_mean

    @property
    def cloud_weight(self) -> float:
        return self.cC * self.cloud_cost_multiplier


def build_scenarios(seed: int = 20260716) -> List[Scenario]:
    scenarios: List[Scenario] = []
    K = 40.0
    mu = 3.0 * K
    qH = 0.40
    beta = 1.0  # equivalent to legacy beta=0.025 when written exp(-beta*x)
    jump_cv = 0.8
    deact_mean = 0.5
    i = 0
    for rho in (0.55, 0.75, 0.90):
        for scv in (1.0, 4.0):
            for mf in (0.05, 0.10):
                for tau in (0.25, 1.0, 4.0):
                    i += 1
                    m = mf * K
                    mH, mL = 1.15 * m, 0.85 * m
                    input_total = rho * mu
                    inputH = qH * input_total
                    inputL = (1.0 - qH) * input_total
                    scenarios.append(Scenario(
                        scenario_id=f"F{i:02d}", design="factorial", K=K,
                        mu_max=mu, rho=rho, arrival_scv=scv,
                        mean_jump_fraction=mf, tau=tau, qH=qH, beta=beta,
                        jump_cv=jump_cv, cloud_cost_multiplier=1.0,
                        deactivation_mean=deact_mean,
                        lambda_H=inputH/mH, lambda_L=inputL/mL,
                        mean_H=mH, mean_L=mL, cv_H=jump_cv, cv_L=jump_cv,
                    ))

    # Maximin-like scrambled Latin hypercube; workload and activation dimensions were
    # already swept in the factorial design and are held at central values here.
    sampler = qmc.LatinHypercube(d=6, seed=seed)
    U = sampler.random(n=24)
    # Improve dispersion by retaining the best of a few random scrambles.
    best = U
    best_min = 0.0
    rng = np.random.default_rng(seed)
    for _ in range(30):
        cand = qmc.LatinHypercube(d=6, seed=int(rng.integers(1, 2**31-1))).random(n=24)
        D = np.sqrt(((cand[:, None, :] - cand[None, :, :])**2).sum(axis=2))
        D[D == 0] = np.inf
        md = float(D.min())
        if md > best_min:
            best, best_min = cand, md
    for j, u in enumerate(best, 1):
        qh = 0.2 + 0.6*u[0]
        b = 0.6 + 0.8*u[1]
        jcv = 0.5 + 1.5*u[2]
        ccm = math.exp(math.log(0.25) + u[3]*(math.log(4.0)-math.log(0.25)))
        dm = 0.25 + 1.75*u[4]
        Kj = 30.0 + 50.0*u[5]
        muj = 3.0*Kj
        rhoj = 0.75
        mf = 0.075
        tauj = 1.0
        scvj = 1.0 if j % 2 else 4.0
        m = mf*Kj
        mH, mL = 1.15*m, 0.85*m
        inp = rhoj*muj
        scenarios.append(Scenario(
            scenario_id=f"R{j:02d}", design="lhs", K=Kj, mu_max=muj,
            rho=rhoj, arrival_scv=scvj, mean_jump_fraction=mf, tau=tauj,
            qH=qh, beta=b, jump_cv=jcv, cloud_cost_multiplier=ccm,
            deactivation_mean=dm,
            lambda_H=(qh*inp)/mH, lambda_L=((1-qh)*inp)/mL,
            mean_H=mH, mean_L=mL, cv_H=jcv, cv_L=jcv,
        ))
    return scenarios


def gamma_tail(remaining: np.ndarray, mean: float, cv: float) -> np.ndarray:
    """Arrival overflow probability P[J > remaining] for a Gamma jump."""
    shape = 1.0/(cv*cv)
    scale = mean/shape
    z = np.maximum(remaining, 0.0)/scale
    out = gammaincc(shape, z)
    out[remaining < 0.0] = 1.0
    return out


def gamma_tail_work_fraction(remaining: np.ndarray, mean: float, cv: float) -> np.ndarray:
    """Fraction of mean workload carried by jumps exceeding ``remaining``.

    For J ~ Gamma(k, theta), E[J 1{J>r}]/E[J] = Q(k+1, r/theta).
    This differs from P[J>r] and is required when converting admission
    probabilities into admitted/offloaded workload rates.
    """
    shape = 1.0/(cv*cv)
    scale = mean/shape
    z = np.maximum(remaining, 0.0)/scale
    out = gammaincc(shape + 1.0, z)
    out[remaining < 0.0] = 1.0
    return out


def stationary_distribution(Q: sparse.csr_matrix) -> np.ndarray:
    n = Q.shape[0]
    A = Q.T.tolil()
    b = np.zeros(n)
    A[-1, :] = np.ones(n)
    b[-1] = 1.0
    p = spsolve(A.tocsr(), b)
    p = np.asarray(p, dtype=float)
    # Tiny negative values are numerical noise. Material negativity is retained for diagnostics.
    p[np.abs(p) < 1e-14] = 0.0
    s = p.sum()
    if not np.isfinite(s) or abs(s) < EPS:
        raise RuntimeError("Stationary solve failed")
    return p/s


def diffusion_generator(s: Scenario, alpha_on: float, alpha_off: float | None = None,
                        N: int = 161, tau_override: float | None = None) -> Tuple[sparse.csr_matrix, np.ndarray]:
    if alpha_off is None:
        alpha_off = alpha_on
    K = s.K
    x = np.linspace(0.0, K, N)
    h = x[1]-x[0]
    nstates = 3*N
    rows: List[int] = []
    cols: List[int] = []
    data: List[float] = []
    m2H = s.mean_H**2*(1.0+s.cv_H**2)
    m2L = s.mean_L**2*(1.0+s.cv_L**2)
    theta = 1.0/(tau_override if tau_override is not None else s.tau)

    def add(i: int, j: int, v: float) -> None:
        if v != 0.0:
            rows.append(i); cols.append(j); data.append(v)

    for n in range(3):
        local_input = s.input_H + (s.input_L if n < 2 else 0.0)
        variance = s.lambda_H*m2H + (s.lambda_L*m2L if n < 2 else 0.0)
        for ix, xx in enumerate(x):
            idx = n*N + ix
            service = s.mu_max*math.exp(-s.beta*xx/K)
            b = -service + local_input
            a = max(variance, 1e-9)
            up = a/(2*h*h) + max(b, 0.0)/h
            down = a/(2*h*h) + max(-b, 0.0)/h
            total = 0.0
            if ix < N-1:
                add(idx, idx+1, up); total += up
            # reflecting boundary: outward rates are suppressed rather than killed
            if ix > 0:
                add(idx, idx-1, down); total += down
            if n == 0 and xx >= alpha_on:
                r = s.lambda_L
                add(idx, N+ix, r); total += r
            elif n == 1:
                add(idx, 2*N+ix, theta); total += theta
            elif n == 2 and xx < alpha_off:
                r = s.mu_c
                add(idx, ix, r); total += r
            add(idx, idx, -total)
    Q = sparse.csr_matrix((data, (rows, cols)), shape=(nstates, nstates))
    return Q, x


def diffusion_metrics(s: Scenario, alpha_on: float, alpha_off: float | None = None,
                      N: int = 161, tau_override: float | None = None) -> Dict[str, float]:
    if alpha_off is None:
        alpha_off = alpha_on
    Q, x = diffusion_generator(s, alpha_on, alpha_off, N=N, tau_override=tau_override)
    p = stationary_distribution(Q)
    P = p.reshape(3, N)
    p_all = P.sum(axis=0)
    remaining = s.K - x
    tailH = gamma_tail(remaining, s.mean_H, s.cv_H)
    tailL = gamma_tail(remaining, s.mean_L, s.cv_L)
    work_tailH = gamma_tail_work_fraction(remaining, s.mean_H, s.cv_H)
    work_tailL = gamma_tail_work_fraction(remaining, s.mean_L, s.cv_L)

    # Arrival-level loss probabilities. Low-privacy overflow before cloud activation
    # is treated as admission loss, not instantaneous cloud service.
    BH = float((p_all * tailH).sum())
    BL = float(((P[0] + P[1]) * tailL).sum())

    # Workload rates use truncated first moments, not acceptance probabilities.
    local_H_rate = s.input_H * float((p_all * (1.0 - work_tailH)).sum())
    local_L_rate = s.input_L * float(((P[0] + P[1]) * (1.0 - work_tailL)).sum())
    admitted = max(local_H_rate + local_L_rate, EPS)
    mean_x = float((p_all * x).sum())
    W = mean_x / admitted

    # In active cloud phase, all new L workload is offloaded.
    cloud_frac = float(P[2].sum())
    cloud_frac = min(max(cloud_frac, 0.0), 1.0)
    overshoot = float((P[1] * np.maximum(x - alpha_on, 0.0)).sum())
    J = s.cW * W + s.cB * BH + s.cL * BL + s.cloud_weight * cloud_frac
    residual = np.asarray(p @ Q).ravel()
    return {
        "mean_x": mean_x, "W": W, "B_H": BH, "B_L": BL,
        "cloud_fraction": cloud_frac, "R_cloud": cloud_frac * s.input_L,
        "overshoot": overshoot, "phase0": float(P[0].sum()),
        "phase1": float(P[1].sum()), "phase2": float(P[2].sum()),
        "objective": J, "mass_error": abs(p.sum() - 1.0),
        "min_probability": float(p.min()),
        "stationary_residual_inf": float(np.max(np.abs(residual))),
    }


def one_phase_diffusion_metrics(s: Scenario, p_offload: float, N: int = 161,
                                overflow_to_cloud: bool = True) -> Dict[str, float]:
    K = s.K
    x = np.linspace(0.0, K, N)
    h = x[1] - x[0]
    local_L = (1.0 - p_offload) * s.input_L
    local_input = s.input_H + local_L
    m2H = s.mean_H**2 * (1 + s.cv_H**2)
    m2L = s.mean_L**2 * (1 + s.cv_L**2)
    variance = s.lambda_H*m2H + (1-p_offload)*s.lambda_L*m2L
    rows=[]; cols=[]; data=[]
    for i, xx in enumerate(x):
        b = -s.mu_max*math.exp(-s.beta*xx/K) + local_input
        a = max(variance, 1e-9)
        up = a/(2*h*h) + max(b,0)/h
        down = a/(2*h*h) + max(-b,0)/h
        total=0
        if i<N-1: rows.append(i); cols.append(i+1); data.append(up); total+=up
        if i>0: rows.append(i); cols.append(i-1); data.append(down); total+=down
        rows.append(i); cols.append(i); data.append(-total)
    Q=sparse.csr_matrix((data,(rows,cols)),shape=(N,N))
    p=stationary_distribution(Q)
    remaining=K-x
    tailH=gamma_tail(remaining,s.mean_H,s.cv_H)
    tailL=gamma_tail(remaining,s.mean_L,s.cv_L)
    work_tailH=gamma_tail_work_fraction(remaining,s.mean_H,s.cv_H)
    work_tailL=gamma_tail_work_fraction(remaining,s.mean_L,s.cv_L)
    BH=float((p*tailH).sum())
    local_L_overflow_prob=(1-p_offload)*float((p*tailL).sum())
    local_L_overflow_work=(1-p_offload)*float((p*work_tailL).sum())
    if overflow_to_cloud:
        BL=0.0
        cloud_frac=min(1.0,p_offload+local_L_overflow_work)
    else:
        BL=local_L_overflow_prob
        cloud_frac=p_offload
    admitted=s.input_H*float((p*(1-work_tailH)).sum()) \
             + s.input_L*(1-p_offload)*float((p*(1-work_tailL)).sum())
    mean_x=float((p*x).sum())
    W=mean_x/max(admitted,EPS)
    J=s.cW*W+s.cB*BH+s.cL*BL+s.cloud_weight*cloud_frac
    return {"mean_x":mean_x,"W":W,"B_H":BH,"B_L":BL,
            "cloud_fraction":cloud_frac,"R_cloud":cloud_frac*s.input_L,
            "overshoot":0.0,"phase0":1.0,"phase1":0.0,
            "phase2":0.0,"objective":J}


def mmpp_q_for_scv(total_lambda: float, target_scv: float, low: float=0.05, high: float=1.95) -> float:
    if target_scv <= 1.000001:
        return math.inf
    def scv(q: float) -> float:
        Q=np.array([[-q,q],[q,-q]],float)
        rates=np.array([low*total_lambda,high*total_lambda])
        pi=np.array([0.5,0.5]); lbar=float((pi*rates).sum())
        alpha=pi*rates/lbar
        S=Q-np.diag(rates); inv=np.linalg.inv(-S); one=np.ones(2)
        m1=float(alpha@inv@one); m2=float(2*alpha@inv@inv@one)
        return m2/m1**2-1.0
    f=lambda logq: scv(math.exp(logq))-target_scv
    return math.exp(brentq(f,math.log(1e-8*total_lambda),math.log(1e4*total_lambda)))


@njit(cache=True)
def _generate_stream(seed: int, horizon: float, lamH: float, lamL: float,
                     meanH: float, meanL: float, cvH: float, cvL: float,
                     arrival_scv: float):
    np.random.seed(seed)
    lam=lamH+lamL
    high_mult=1.95; low_mult=0.05
    if arrival_scv > 1.1:
        # For this two-state symmetric MMPP, q/lambda=0.252083333... gives SCV 4.
        q=0.2520833333333333*lam
        max_rate=high_mult*lam+q
    else:
        q=0.0; max_rate=lam
    max_events=int(max(1000.0, max_rate*horizon*1.35 + 20.0*math.sqrt(max_rate*horizon+1.0)))
    times=np.empty(max_events,np.float64)
    classes=np.empty(max_events,np.int8)
    jumps=np.empty(max_events,np.float64)
    uniforms=np.empty(max_events,np.float64)
    t=0.0; n=0; env=1
    shapeH=1.0/(cvH*cvH); scaleH=meanH/shapeH
    shapeL=1.0/(cvL*cvL); scaleL=meanL/shapeL
    while t < horizon and n < max_events:
        if arrival_scv <= 1.1:
            t += np.random.exponential(1.0/lam)
            if t >= horizon: break
            isH = np.random.random() < lamH/lam
        else:
            rate=(high_mult if env==1 else low_mult)*lam
            total=rate+q
            t += np.random.exponential(1.0/total)
            if t >= horizon: break
            if np.random.random() < q/total:
                env=1-env
                continue
            isH = np.random.random() < lamH/lam
        times[n]=t
        classes[n]=0 if isH else 1
        jumps[n]=np.random.gamma(shapeH,scaleH) if isH else np.random.gamma(shapeL,scaleL)
        uniforms[n]=np.random.random()
        n += 1
    return times[:n], classes[:n], jumps[:n], uniforms[:n]


@njit(cache=True)
def _decay_and_integrals(x0: float, dt: float, K: float, mu: float, beta: float,
                         level: float):
    """Return x1, integral x dt, and integral max(x-level,0) dt."""
    if dt <= 0.0 or x0 <= 0.0:
        return max(x0,0.0), 0.0, 0.0
    y0=math.exp(beta*x0/K)
    c=beta*mu/K
    y1=max(1.0,y0-c*dt)
    x1=(K/beta)*math.log(y1)
    F0=y0*math.log(y0)-y0
    F1=y1*math.log(y1)-y1
    intx=(K/beta)/c*(F0-F1)
    # Above-level integral over the portion before crossing.
    if x0 <= level:
        inta=0.0
    else:
        yl=math.exp(beta*level/K)
        yend=max(y1,yl)
        Fend=yend*math.log(yend)-yend
        dt_above=(y0-yend)/c
        inta=(K/beta)/c*(F0-Fend)-level*dt_above
        if inta < 0.0 and inta > -1e-10: inta=0.0
    return x1,intx,inta


@njit(cache=True)
def _time_to_level(x: float, level: float, K: float, mu: float, beta: float):
    if x <= level: return 0.0
    return (K/(beta*mu))*(math.exp(beta*x/K)-math.exp(beta*level/K))


@njit(cache=True)
def _simulate_threshold(times, classes, jumps, uniforms, horizon: float, burn: float,
                        K: float, mu: float, beta: float, alpha_on: float, alpha_off: float,
                        tau: float, deact_mean: float, inputH: float, inputL: float,
                        cW: float, cB: float, cL: float, cC: float, rng_seed: int):
    np.random.seed(rng_seed)
    # State and phase-event clocks.
    x=0.0; phase=0; t=0.0; idx=0
    activation_time=1e300; deact_time=1e300; crossing_time=1e300
    sumx=0.0; sumover=0.0; phase_time=np.zeros(3,np.float64)
    H_arr=0; H_block=0; L_arr=0; L_block=0
    H_work=0.0; L_local_work=0.0; cloud_work=0.0
    activations=0
    n=len(times)
    while t < horizon:
        next_arr=times[idx] if idx<n else 1e300
        # If active and above off threshold, schedule deterministic crossing.
        if phase==2 and x>alpha_off and crossing_time>1e299 and deact_time>1e299:
            crossing_time=t+_time_to_level(x,alpha_off,K,mu,beta)
        te=min(next_arr,activation_time,deact_time,crossing_time,horizon)
        dt=te-t
        if dt>0:
            x1,intx,intover=_decay_and_integrals(x,dt,K,mu,beta,alpha_on)
            if te>burn:
                # Split at burn if the interval straddles burn.
                if t>=burn:
                    sumx += intx
                    if phase==1: sumover += intover
                    phase_time[phase] += dt
                else:
                    post=te-burn
                    xb,_,_=_decay_and_integrals(x,burn-t,K,mu,beta,alpha_on)
                    _,intpost,overpost=_decay_and_integrals(xb,post,K,mu,beta,alpha_on)
                    sumx += intpost
                    if phase==1: sumover += overpost
                    phase_time[phase] += post
            x=x1; t=te
        if t>=horizon-1e-12: break
        # Process event; tie order: phase completions, crossings, then arrival.
        if abs(t-activation_time)<1e-10:
            phase=2; activation_time=1e300; deact_time=1e300; crossing_time=1e300
            if x<=alpha_off:
                deact_time=t+np.random.exponential(deact_mean)
            continue
        if abs(t-crossing_time)<1e-10:
            crossing_time=1e300
            if phase==2:
                x=min(x,alpha_off)
            if phase==2 and x<=alpha_off+1e-9:
                deact_time=t+np.random.exponential(deact_mean)
            continue
        if abs(t-deact_time)<1e-10:
            phase=0; deact_time=1e300; crossing_time=1e300
            continue
        if idx<n and abs(t-next_arr)<1e-10:
            cls=classes[idx]; j=jumps[idx]
            if cls==0:
                if t>=burn: H_arr += 1
                if x+j<=K:
                    x += j
                    if t>=burn: H_work += j
                else:
                    if t>=burn: H_block += 1
                if phase==2:
                    # Arrival may cancel a pending deactivation.
                    if x>alpha_off:
                        deact_time=1e300
                        crossing_time=t+_time_to_level(x,alpha_off,K,mu,beta)
            else:
                if t>=burn: L_arr += 1
                if phase==2:
                    if t>=burn: cloud_work += j
                else:
                    if phase==0 and x>=alpha_on:
                        phase=1; activations += 1
                        activation_time=t+np.random.exponential(tau)
                    if x+j<=K:
                        x += j
                        if t>=burn: L_local_work += j
                    else:
                        # Cloud is not yet available; the request is rejected.
                        if phase==0:
                            phase=1; activations += 1
                            activation_time=t+np.random.exponential(tau)
                        if t>=burn: L_block += 1
            idx += 1
            continue
    obs=max(horizon-burn,EPS)
    meanx=sumx/obs
    admitted=(H_work+L_local_work)/obs
    W=meanx/max(admitted,EPS)
    BH=H_block/max(H_arr,1)
    BL=L_block/max(L_arr,1)
    cloud_frac=(cloud_work/obs)/max(inputL,EPS)
    if cloud_frac<0: cloud_frac=0.0
    if cloud_frac>1: cloud_frac=1.0
    obj=cW*W+cB*BH+cL*BL+cC*cloud_frac
    return np.array([meanx,W,BH,BL,cloud_frac,cloud_work/obs,sumover/obs,
                     phase_time[0]/obs,phase_time[1]/obs,phase_time[2]/obs,obj,
                     activations/obs,H_arr,H_block,L_arr,L_block],dtype=np.float64)


@njit(cache=True)
def _simulate_random(times, classes, jumps, uniforms, horizon: float, burn: float,
                     K: float, mu: float, beta: float, p_off: float,
                     overflow_to_cloud: bool, inputH: float, inputL: float,
                     cW: float, cB: float, cL: float, cC: float):
    x=0.0; t=0.0; sumx=0.0
    H_arr=0; H_block=0; L_arr=0; L_block=0
    H_work=0.0; L_local_work=0.0; cloud_work=0.0
    for idx in range(len(times)):
        te=times[idx]
        if te>horizon: break
        dt=te-t
        x1,intx,_=_decay_and_integrals(x,dt,K,mu,beta,0.0)
        if te>burn:
            if t>=burn: sumx += intx
            else:
                xb,_,_=_decay_and_integrals(x,burn-t,K,mu,beta,0.0)
                _,ip,_=_decay_and_integrals(xb,te-burn,K,mu,beta,0.0)
                sumx += ip
        x=x1; t=te
        cls=classes[idx]; j=jumps[idx]
        if cls==0:
            if t>=burn: H_arr += 1
            if x+j<=K:
                x+=j
                if t>=burn: H_work+=j
            elif t>=burn: H_block += 1
        else:
            if t>=burn: L_arr += 1
            if uniforms[idx]<p_off:
                if t>=burn: cloud_work += j
            elif x+j<=K:
                x+=j
                if t>=burn: L_local_work += j
            elif overflow_to_cloud:
                if t>=burn: cloud_work += j
            elif t>=burn:
                L_block += 1
    if t<horizon:
        x1,intx,_=_decay_and_integrals(x,horizon-t,K,mu,beta,0.0)
        if horizon>burn:
            if t>=burn: sumx+=intx
            else:
                xb,_,_=_decay_and_integrals(x,burn-t,K,mu,beta,0.0)
                _,ip,_=_decay_and_integrals(xb,horizon-burn,K,mu,beta,0.0)
                sumx+=ip
    obs=max(horizon-burn,EPS)
    meanx=sumx/obs; admitted=(H_work+L_local_work)/obs
    W=meanx/max(admitted,EPS); BH=H_block/max(H_arr,1); BL=L_block/max(L_arr,1)
    cloud_frac=(cloud_work/obs)/max(inputL,EPS); cloud_frac=min(max(cloud_frac,0.0),1.0)
    obj=cW*W+cB*BH+cL*BL+cC*cloud_frac
    return np.array([meanx,W,BH,BL,cloud_frac,cloud_work/obs,0.0,1.0,0.0,0.0,obj,0.0,
                     H_arr,H_block,L_arr,L_block],dtype=np.float64)


@njit(cache=True)
def _simulate_random_activation(times, classes, jumps, uniforms, horizon: float, burn: float,
                                K: float, mu: float, beta: float, p_trigger: float,
                                tau: float, active_mean: float, inputH: float, inputL: float,
                                cW: float, cB: float, cL: float, cC: float, rng_seed: int):
    """State-oblivious cloud activation with the same startup delay.

    Each low-privacy arrival in phase 0 triggers activation with probability p_trigger.
    During activation, requests remain local if they fit. Once active, all low-privacy
    arrivals are offloaded for an exponential active period. This is a fairer random
    baseline than assuming an always-warm cloud endpoint.
    """
    np.random.seed(rng_seed)
    x=0.0; phase=0; t=0.0; idx=0
    activation_time=1e300; deact_time=1e300
    sumx=0.0; phase_time=np.zeros(3,np.float64)
    H_arr=0; H_block=0; L_arr=0; L_block=0
    H_work=0.0; L_local_work=0.0; cloud_work=0.0
    activations=0
    n=len(times)
    while t<horizon:
        next_arr=times[idx] if idx<n else 1e300
        te=min(next_arr,activation_time,deact_time,horizon)
        dt=te-t
        if dt>0:
            x1,intx,_=_decay_and_integrals(x,dt,K,mu,beta,0.0)
            if te>burn:
                if t>=burn:
                    sumx+=intx; phase_time[phase]+=dt
                else:
                    xb,_,_=_decay_and_integrals(x,burn-t,K,mu,beta,0.0)
                    _,ip,_=_decay_and_integrals(xb,te-burn,K,mu,beta,0.0)
                    sumx+=ip; phase_time[phase]+=te-burn
            x=x1; t=te
        if t>=horizon-1e-12: break
        if abs(t-activation_time)<1e-10:
            phase=2; activation_time=1e300
            deact_time=t+np.random.exponential(active_mean)
            continue
        if abs(t-deact_time)<1e-10:
            phase=0; deact_time=1e300
            continue
        if idx<n and abs(t-next_arr)<1e-10:
            cls=classes[idx]; j=jumps[idx]
            if cls==0:
                if t>=burn: H_arr+=1
                if x+j<=K:
                    x+=j
                    if t>=burn: H_work+=j
                elif t>=burn: H_block+=1
            else:
                if t>=burn: L_arr+=1
                if phase==2:
                    if t>=burn: cloud_work+=j
                else:
                    if phase==0 and uniforms[idx]<p_trigger:
                        phase=1; activations+=1
                        activation_time=t+np.random.exponential(tau)
                    if x+j<=K:
                        x+=j
                        if t>=burn: L_local_work+=j
                    else:
                        if phase==0:
                            phase=1; activations+=1
                            activation_time=t+np.random.exponential(tau)
                        if t>=burn: L_block+=1
            idx+=1
            continue
    obs=max(horizon-burn,EPS)
    meanx=sumx/obs; admitted=(H_work+L_local_work)/obs
    W=meanx/max(admitted,EPS); BH=H_block/max(H_arr,1); BL=L_block/max(L_arr,1)
    cloud_frac=(cloud_work/obs)/max(inputL,EPS); cloud_frac=min(max(cloud_frac,0.0),1.0)
    obj=cW*W+cB*BH+cL*BL+cC*cloud_frac
    return np.array([meanx,W,BH,BL,cloud_frac,cloud_work/obs,0.0,
                     phase_time[0]/obs,phase_time[1]/obs,phase_time[2]/obs,obj,
                     activations/obs,H_arr,H_block,L_arr,L_block],dtype=np.float64)


METRIC_NAMES=["mean_x","W","B_H","B_L","cloud_fraction","R_cloud","overshoot",
              "phase0","phase1","phase2","objective","activation_rate",
              "H_arrivals","H_blocks","L_arrivals","L_blocks"]
CORE_METRICS=METRIC_NAMES[:12]


def generate_stream(s: Scenario, seed: int, horizon: float):
    return _generate_stream(seed,horizon,s.lambda_H,s.lambda_L,s.mean_H,s.mean_L,
                            s.cv_H,s.cv_L,s.arrival_scv)


def sim_threshold(s: Scenario, stream, horizon: float, burn: float,
                  alpha_on: float, alpha_off: float | None=None, seed: int=1) -> Dict[str,float]:
    if alpha_off is None: alpha_off=alpha_on
    # Phase-duration draws are policy-dependent; reset NumPy's Numba RNG deterministically.
    np.random.seed(seed)
    arr=_simulate_threshold(*stream,horizon,burn,s.K,s.mu_max,s.beta,alpha_on,alpha_off,
                            s.tau,s.deactivation_mean,s.input_H,s.input_L,s.cW,s.cB,s.cL,s.cloud_weight,seed)
    return dict(zip(METRIC_NAMES,map(float,arr)))


def sim_random(s: Scenario, stream, horizon: float, burn: float, p_off: float,
               overflow_to_cloud: bool = True) -> Dict[str,float]:
    arr=_simulate_random(*stream,horizon,burn,s.K,s.mu_max,s.beta,p_off,overflow_to_cloud,
                         s.input_H,s.input_L,s.cW,s.cB,s.cL,s.cloud_weight)
    return dict(zip(METRIC_NAMES,map(float,arr)))



def sim_random_activation(s: Scenario, stream, horizon: float, burn: float,
                          p_trigger: float, seed: int=1) -> Dict[str,float]:
    arr=_simulate_random_activation(*stream,horizon,burn,s.K,s.mu_max,s.beta,p_trigger,
                                    s.tau,s.deactivation_mean,s.input_H,s.input_L,
                                    s.cW,s.cB,s.cL,s.cloud_weight,seed)
    return dict(zip(METRIC_NAMES,map(float,arr)))

def mean_ci(values: np.ndarray, confidence: float=0.95) -> Tuple[float,float]:
    values=np.asarray(values,float)
    n=len(values); m=float(values.mean())
    if n<2: return m,float("nan")
    se=float(values.std(ddof=1)/math.sqrt(n))
    return m,float(student_t.ppf((1+confidence)/2,n-1)*se)


def optimize_diffusion(s: Scenario, thresholds: np.ndarray, N: int=161,
                       alpha_off_gap: float=0.0, tau_override: float | None=None):
    rows=[]
    for a in thresholds:
        off=max(0.02*s.K,a-alpha_off_gap)
        met=diffusion_metrics(s,a,off,N=N,tau_override=tau_override)
        rows.append({"alpha":a,"alpha_off":off,**met})
    df=pd.DataFrame(rows)
    return df, float(df.loc[df.objective.idxmin(),"alpha"])


def evaluate_threshold_grid_jump(s: Scenario, thresholds: np.ndarray, streams: List[Tuple],
                                 horizon: float,burn: float,seed_base: int,
                                 off_gap: float=0.0):
    rows=[]
    for a in thresholds:
        vals=[]
        for r,stream in enumerate(streams):
            vals.append(sim_threshold(s,stream,horizon,burn,a,max(0.02*s.K,a-off_gap),seed_base+1009*r))
        row={"alpha":a,"alpha_off":max(0.02*s.K,a-off_gap)}
        for name in CORE_METRICS: row[name]=float(np.mean([v[name] for v in vals]))
        rows.append(row)
    df=pd.DataFrame(rows)
    return df,float(df.loc[df.objective.idxmin(),"alpha"])


def campaign(args):
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    all_scenarios=build_scenarios(args.seed)
    start=max(args.start_scenario,0)
    scenarios=all_scenarios[start:]
    if args.max_scenarios is not None:
        scenarios=scenarios[:args.max_scenarios]
    pd.DataFrame([asdict(s) for s in scenarios]).to_csv(out/"scenarios.csv",index=False)
    thresholds_by_id={s.scenario_id:np.linspace(0.05*s.K,0.95*s.K,args.n_thresholds) for s in scenarios}
    all_curves=[]; final_rows=[]; scenario_summary=[]; verification=[]
    t0=time.time()

    # Trigger Numba compilation with a tiny stream before timing substantive work.
    s0=scenarios[0]
    tiny=generate_stream(s0,args.seed,5.0)
    sim_threshold(s0,tiny,5.0,1.0,0.5*s0.K,seed=args.seed)
    sim_random(s0,tiny,5.0,1.0,0.2)

    for local_i,s in enumerate(scenarios,1):
        si=start+local_i
        th=thresholds_by_id[s.scenario_id]
        # Diffusion curves: proposed, delay-unaware, and optimized spatial hysteresis.
        dcurve,aD=optimize_diffusion(s,th,N=args.grid_n)
        dcurve.insert(0,"scenario_id",s.scenario_id); dcurve.insert(1,"model","diffusion")
        all_curves.append(dcurve)
        _,aDU=optimize_diffusion(s,th,N=args.grid_n,tau_override=0.02)
        hcurve,aH=optimize_diffusion(s,th,N=args.grid_n,alpha_off_gap=0.10*s.K)

        # Numerical verification at selected threshold and on a doubled grid.
        md=diffusion_metrics(s,aD,aD,N=args.grid_n)
        md2=diffusion_metrics(s,aD,aD,N=2*args.grid_n-1)
        verification.append({
            "scenario_id":s.scenario_id,"alpha_D":aD,
            "mass_error":md["mass_error"],"min_probability":md["min_probability"],
            "stationary_residual_inf":md["stationary_residual_inf"],
            "grid_change_W":abs(md2["W"]-md["W"])/max(abs(md2["W"]),EPS),
            "grid_change_B_H":abs(md2["B_H"]-md["B_H"])/max(abs(md2["B_H"]),1e-8),
            "grid_change_cloud":abs(md2["cloud_fraction"]-md["cloud_fraction"])/max(abs(md2["cloud_fraction"]),1e-8),
        })

        # Final independent exogenous streams are shared across all policies and
        # across the jump-threshold grid (common random numbers).
        streams=[generate_stream(s,args.seed+9000000+100000*si+137*r,args.final_horizon)
                 for r in range(args.final_reps)]
        jcurve,aJ=evaluate_threshold_grid_jump(s,th,streams,args.final_horizon,
                                               args.final_burn,args.seed+700000*si)
        jcurve.insert(0,"scenario_id",s.scenario_id); jcurve.insert(1,"model","jump_final")
        all_curves.append(jcurve)

        # Budget-matched random probability from the proposed diffusion policy.
        dstar=dcurve.iloc[(dcurve.alpha-aD).abs().argmin()]
        p_budget=float(np.clip(dstar.cloud_fraction,0,1))

        policies={
            "local_only":("local",0.0,0.0),
            "budget_random":("random",p_budget,0.0),
            "static_half":("threshold",0.5*s.K,0.5*s.K),
            "delay_unaware":("threshold",aDU,aDU),
            "hysteretic":("threshold",aH,max(0.02*s.K,aH-0.10*s.K)),
            "diffusion_optimal":("threshold",aD,aD),
            "jump_oracle":("threshold",aJ,aJ),
        }
        per_policy={}
        for pname,(kind,v1,v2) in policies.items():
            reps=[]
            for r,stream in enumerate(streams):
                if kind=="random":
                    reps.append(sim_random(s,stream,args.final_horizon,args.final_burn,v1,True))
                elif kind=="local":
                    reps.append(sim_random(s,stream,args.final_horizon,args.final_burn,0.0,False))
                else:
                    reps.append(sim_threshold(s,stream,args.final_horizon,args.final_burn,v1,v2,
                                              args.seed+700000*si+1009*r))
            per_policy[pname]=reps
            row={"scenario_id":s.scenario_id,"design":s.design,"policy":pname,
                 "alpha_on":v1 if kind=="threshold" else np.nan,
                 "alpha_off":v2 if kind=="threshold" else np.nan,
                 "p_offload":v1 if kind=="random" else np.nan,
                 "n_rep":args.final_reps}
            for name in CORE_METRICS:
                m,hw=mean_ci(np.array([z[name] for z in reps]))
                row[name]=m; row[name+"_ci95_hw"]=hw
            final_rows.append(row)

        # Policy-level validation on final streams.
        dvals=np.array([z["objective"] for z in per_policy["diffusion_optimal"]])
        jvals=np.array([z["objective"] for z in per_policy["jump_oracle"]])
        regret=float((dvals.mean()-jvals.mean())/max(jvals.mean(),EPS))
        regret=max(regret,0.0)
        # Compare diffusion-predicted ordering with final jump ordering for the five deployable policies.
        deploy=["local_only","budget_random","static_half","delay_unaware","hysteretic","diffusion_optimal"]
        diff_obj={}
        diff_obj["local_only"]=one_phase_diffusion_metrics(s,0.0,N=args.grid_n,overflow_to_cloud=False)["objective"]
        diff_obj["budget_random"]=one_phase_diffusion_metrics(s,p_budget,N=args.grid_n)["objective"]
        diff_obj["static_half"]=diffusion_metrics(s,0.5*s.K,0.5*s.K,N=args.grid_n)["objective"]
        diff_obj["delay_unaware"]=diffusion_metrics(s,aDU,aDU,N=args.grid_n)["objective"]
        diff_obj["hysteretic"]=diffusion_metrics(s,aH,max(0.02*s.K,aH-0.1*s.K),N=args.grid_n)["objective"]
        diff_obj["diffusion_optimal"]=diffusion_metrics(s,aD,aD,N=args.grid_n)["objective"]
        jump_obj={p:float(np.mean([z["objective"] for z in per_policy[p]])) for p in deploy}
        tau_rank=float(kendalltau([diff_obj[p] for p in deploy],[jump_obj[p] for p in deploy]).statistic)
        top_agree=min(diff_obj,key=diff_obj.get)==min(jump_obj,key=jump_obj.get)

        # Metric error at alpha_D: diffusion vs final jump results.
        jm={name:float(np.mean([z[name] for z in per_policy["diffusion_optimal"]])) for name in CORE_METRICS}
        errs={name:abs(md[name]-jm[name])/max(abs(jm[name]),1e-8) for name in ["W","B_H","cloud_fraction","overshoot"]}
        scenario_summary.append({
            "scenario_id":s.scenario_id,"design":s.design,"rho":s.rho,"arrival_scv":s.arrival_scv,
            "mean_jump_fraction":s.mean_jump_fraction,"tau":s.tau,"qH":s.qH,"beta":s.beta,
            "jump_cv":s.jump_cv,"cloud_cost_multiplier":s.cloud_cost_multiplier,"K":s.K,
            "alpha_D":aD,"alpha_J":aJ,"alpha_delay_unaware":aDU,"alpha_hysteretic":aH,
            "threshold_error_fraction":abs(aD-aJ)/s.K,"policy_regret":regret,
            "rank_kendall_tau":tau_rank,"top_policy_agreement":int(top_agree),
            "error_W":errs["W"],"error_B_H":errs["B_H"],
            "error_cloud_fraction":errs["cloud_fraction"],"error_overshoot":errs["overshoot"],
            "p_budget_random":p_budget,
        })
        elapsed=time.time()-t0
        print(f"[{local_i:02d}/{len(scenarios)} | global {si:02d}] {s.scenario_id}: aD={aD:.3g}, aJ={aJ:.3g}, "
              f"regret={regret:.3%}, elapsed={elapsed:.1f}s",flush=True)

    curves=pd.concat(all_curves,ignore_index=True)
    finals=pd.DataFrame(final_rows)
    summary=pd.DataFrame(scenario_summary)
    ver=pd.DataFrame(verification)
    curves.to_csv(out/"threshold_curves.csv",index=False)
    finals.to_csv(out/"policy_results.csv",index=False)
    summary.to_csv(out/"validation_summary.csv",index=False)
    ver.to_csv(out/"solver_verification.csv",index=False)

    # Aggregate summary and gates.
    metric_err=np.concatenate([summary[c].values for c in ["error_W","error_B_H","error_cloud_fraction"]])
    gates={
        "scenario_count":int(len(summary)),
        "median_principal_metric_error":float(np.median(metric_err)),
        "p90_principal_metric_error":float(np.quantile(metric_err,0.9)),
        "median_policy_regret":float(summary.policy_regret.median()),
        "p90_policy_regret":float(summary.policy_regret.quantile(0.9)),
        "top_policy_agreement":float(summary.top_policy_agreement.mean()),
        "median_kendall_tau":float(summary.rank_kendall_tau.median()),
        "median_threshold_error_fraction":float(summary.threshold_error_fraction.median()),
        "p90_threshold_error_fraction":float(summary.threshold_error_fraction.quantile(0.9)),
        "max_mass_error":float(ver.mass_error.max()),
        "min_probability":float(ver.min_probability.min()),
        "max_stationary_residual":float(ver.stationary_residual_inf.max()),
        "max_grid_change_W":float(ver.grid_change_W.max()),
        "elapsed_seconds":float(time.time()-t0),
    }
    gates["pass_metric_median"]=gates["median_principal_metric_error"]<=0.10
    gates["pass_metric_p90"]=gates["p90_principal_metric_error"]<=0.20
    gates["pass_regret_median"]=gates["median_policy_regret"]<=0.05
    gates["pass_regret_p90"]=gates["p90_policy_regret"]<=0.10
    gates["pass_top_agreement"]=gates["top_policy_agreement"]>=0.80
    gates["pass_rank"]=gates["median_kendall_tau"]>=0.80
    with open(out/"campaign_summary.json","w") as f: json.dump(gates,f,indent=2)
    print(json.dumps(gates,indent=2))


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="results")
    p.add_argument("--seed",type=int,default=20260716)
    p.add_argument("--grid-n",type=int,default=121)
    p.add_argument("--n-thresholds",type=int,default=17)
    p.add_argument("--pilot-reps",type=int,default=3)
    p.add_argument("--pilot-horizon",type=float,default=700.0)
    p.add_argument("--pilot-burn",type=float,default=175.0)
    p.add_argument("--final-reps",type=int,default=20)
    p.add_argument("--final-horizon",type=float,default=900.0)
    p.add_argument("--final-burn",type=float,default=225.0)
    p.add_argument("--max-scenarios",type=int,default=None)
    p.add_argument("--start-scenario",type=int,default=0)
    return p.parse_args()

if __name__=="__main__":
    campaign(parse_args())
