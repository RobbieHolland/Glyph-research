"""Verbatim numerical routines extracted from MHG; see source_provenance.json."""
import warnings
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.special import expit
from scipy.optimize import brentq
from scipy.stats import norm
from sklearn.model_selection import StratifiedKFold

def fmr_crossfit_splits(Y, n_splits=5, inner_splits=None, random_state=42):
    """Choose feasible nested study-stratified folds from class counts only.

    Retain the requested counts whenever feasible, otherwise use2x2. Every
    inner classifier training set must still contain both outcome classes.
    Four events can support2x2; fewer events need not support this design.
    """
    y = np.asarray(Y, dtype=int)
    inner_splits = n_splits if inner_splits is None else inner_splits
    candidates = list(dict.fromkeys([(n_splits, inner_splits), (2, 2)]))
    for outer_count, inner_count in candidates:
        if min(outer_count, inner_count) < 2 or np.bincount(y, minlength=2).min() < outer_count:
            continue
        outer = StratifiedKFold(outer_count, shuffle=True, random_state=random_state)
        feasible = True
        for fold, (tr, _) in enumerate(outer.split(np.zeros(len(y)), y)):
            if np.bincount(y[tr], minlength=2).min() < inner_count:
                feasible = False
                break
            inner = StratifiedKFold(inner_count, shuffle=True, random_state=random_state + fold + 1)
            if any(np.unique(y[tr][itr]).size < 2 for itr, _ in inner.split(np.zeros(len(tr)), y[tr])):
                feasible = False
                break
        if feasible:
            return outer_count, inner_count
    raise ValueError("Outcome classes cannot support nested cross-fitting with at least two folds.")

def fmr_orthogonal(
    T, Y, W, n_splits=5, n_estimators=100, max_depth=4,
    inner_splits=None, *, device="cpu", random_state=42, groups=None,
    return_influence=False, min_child_weight=1, reg_lambda=1,
):
    """Experimental FMR sigmoid estimator with full-model variance weights.

    Model: P(Y=1|T,W) = expit(theta*T + r(W)). The orthogonal score is
    (Y - expit(theta*T + r(W))) * (T - m(W)), where
    m(W) = E[v*T|W] / E[v|W] and v = mu(T,W)*(1-mu(T,W)).
    Unlike weights calculated from r(W) alone, these weights depend on T.
    All nuisance fitting is confined to each outer training fold.
    min_child_weight and reg_lambda control XGBoost nuisance regularization;
    their defaults preserve the original XGBoost settings.

    Returns the conditional OR per input unit of T (no standardization),
    Wald p-value, and 95% CI for independent observations. Supplying groups
    keeps each group within a fold at both nesting levels and uses a
    group-clustered sandwich standard error. Orthogonality
    requires consistent nuisance fits and appropriate convergence rates;
    successful point recovery alone does not establish valid CI coverage.
    With independent observations, infeasible requested folds fall back to2x2
    based only on outcome class support, including every inner training set.
    """
    T = np.asarray(T, dtype=float)
    Y = np.asarray(Y)
    W = np.asarray(W, dtype=float)
    if T.ndim != 1 or Y.ndim != 1:
        raise ValueError("T and Y must be one-dimensional.")
    if W.ndim == 1:
        W = W[:, None]
    if W.ndim != 2 or not (len(T) == len(Y) == len(W)):
        raise ValueError("W must be a matrix with the same row count as T and Y.")
    if not (np.isfinite(T).all() and np.isfinite(W).all()):
        raise ValueError("T and W must contain finite values.")
    if not np.isin(Y, [0, 1]).all():
        raise ValueError("Y must contain only 0 and 1.")
    Y = Y.astype(int)
    inner_splits = n_splits if inner_splits is None else inner_splits
    if n_splits < 2 or inner_splits < 2:
        raise ValueError("Both split counts must be at least 2.")
    if groups is not None:
        groups = np.asarray(groups)
        if groups.ndim != 1 or len(groups) != len(Y) or pd.isna(groups).any():
            raise ValueError("groups must have one nonmissing value per observation.")

    keys = (
        "dml_odds_ratio", "dml_odds_ratio_p_value",
        "dml_odds_ratio_ci_lower", "dml_odds_ratio_ci_upper",
    )
    params = dict(
        tree_method="hist", device=device, n_estimators=n_estimators,
        max_depth=max_depth, verbosity=0, random_state=random_state, n_jobs=1,
        min_child_weight=min_child_weight, reg_lambda=reg_lambda,
    )

    def check_classes(y, folds):
        if np.bincount(y, minlength=2).min() < folds:
            raise ValueError("Too few observations in one outcome class for the requested folds.")

    def make_splits(w, y, group_values, folds, seed):
        if group_values is None:
            splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
            return splitter.split(w, y)
        from sklearn.model_selection import StratifiedGroupKFold
        if len(np.unique(group_values)) < folds:
            raise ValueError("Too few independent groups for the requested folds.")
        splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
        return splitter.split(w, y, group_values)

    try:
        if groups is None:
            selected = fmr_crossfit_splits(Y, n_splits, inner_splits, random_state)
            if selected != (n_splits, inner_splits):
                warnings.warn(
                    f"fmr_orthogonal: using {selected[0]} outer/{selected[1]} inner folds "
                    f"instead of {n_splits}/{inner_splits} because of outcome class counts.",
                    RuntimeWarning,
                )
            n_splits, inner_splits = selected
        check_classes(Y, n_splits)
        if np.var(T) <= 0:
            raise ValueError("T has no variation.")
        n = len(T)
        r_oof = np.empty(n)
        m_oof = np.empty(n)
        outer = make_splits(W, Y, groups, n_splits, random_state)
        for fold, (tr, te) in enumerate(outer):
            T_tr, Y_tr, W_tr = T[tr], Y[tr], W[tr]
            check_classes(Y_tr, inner_splits)
            inner_groups = None if groups is None else groups[tr]
            inner = make_splits(W_tr, Y_tr, inner_groups, inner_splits, random_state + fold + 1)
            pseudo = np.empty(len(tr))
            a_inner = np.empty(len(tr))
            a_test_predictions = []
            for itr, ite in inner:
                full = xgb.XGBClassifier(
                    **params, objective="binary:logistic", eval_metric="logloss",
                ).fit(np.column_stack([T_tr[itr], W_tr[itr]]), Y_tr[itr])
                # Raw margins avoid clipping probabilities before taking logit.
                pseudo[ite] = full.predict(
                    np.column_stack([T_tr[ite], W_tr[ite]]), output_margin=True,
                )
                a_model = xgb.XGBRegressor(
                    **params, objective="reg:squarederror",
                ).fit(W_tr[itr], T_tr[itr])
                a_inner[ite] = a_model.predict(W_tr[ite])
                a_test_predictions.append(a_model.predict(W[te]))

            residual_T = T_tr - a_inner
            denominator = np.sum(residual_T**2)
            if not np.isfinite(denominator) or denominator <= 0:
                raise ValueError("No residual exposure variation in an outer training fold.")
            beta_preliminary = np.sum(pseudo * residual_T) / denominator
            baseline_model = xgb.XGBRegressor(
                **params, objective="reg:squarederror",
            ).fit(W_tr, pseudo)
            a_test = np.mean(a_test_predictions, axis=0)
            r_oof[te] = baseline_model.predict(W[te]) - beta_preliminary * a_test

            # Inner OOF logits approximate theta0*T + r0(W), not just r0(W).
            v_train = expit(pseudo) * expit(-pseudo)
            if not np.isfinite(v_train).all() or np.any(v_train <= 0):
                raise FloatingPointError("Degenerate full-model variance weights.")
            # Preserves the population target. In a regularized learner this
            # also fixes the weight scale relative to its penalty parameters.
            v_train = v_train / np.mean(v_train)
            weighted_model = xgb.XGBRegressor(
                **params, objective="reg:squarederror",
            ).fit(W_tr, T_tr, sample_weight=v_train)
            m_oof[te] = weighted_model.predict(W[te])

        if not (np.isfinite(r_oof).all() and np.isfinite(m_oof).all()):
            raise FloatingPointError("Non-finite nuisance predictions.")
        residual_T = T - m_oof

        def score(theta):
            return np.mean((Y - expit(theta * T + r_oof)) * residual_T)

        if not score(-20.0) * score(20.0) < 0:
            raise ValueError("No sign-changing root bracket in [-20, 20].")
        theta_hat = brentq(score, -20.0, 20.0, maxiter=200)
        eta = theta_hat * T + r_oof
        psi = (Y - expit(eta)) * residual_T
        jacobian = -np.mean(expit(eta) * expit(-eta) * T * residual_T)
        if not np.isfinite(jacobian) or jacobian >= -1e-12:
            raise ValueError("Degenerate or incorrectly signed score derivative.")
        if groups is None:
            influence_ids = np.arange(n)
            influence = -(psi - psi.mean()) / (n * jacobian)
            se = np.sqrt(np.mean((psi - psi.mean())**2) / n) / abs(jacobian)
        else:
            group_codes, influence_ids = pd.factorize(groups)
            n_groups = len(influence_ids)
            if n_groups < 2:
                raise ValueError("At least two independent groups are required.")
            cluster_scores = np.bincount(group_codes, weights=psi)
            influence = -cluster_scores / (n * jacobian) * np.sqrt(n_groups / (n_groups - 1))
            se = np.sqrt(np.sum(influence**2))
        if not np.isfinite(se) or se <= 0:
            raise FloatingPointError("Invalid standard error.")
        p_value = 2 * norm.sf(abs(theta_hat / se))
        critical = norm.ppf(0.975)
        with np.errstate(over="ignore", under="ignore"):
            odds_ratio, lower, upper = np.exp([
                theta_hat, theta_hat - critical * se, theta_hat + critical * se,
            ])
        result = dict(zip(keys, map(float, [odds_ratio, p_value, lower, upper])))
        if return_influence:
            result['_patient_ids'] = np.asarray(influence_ids)
            result['_cluster_influence'] = influence
        return result
    except (ValueError, RuntimeError, FloatingPointError, xgb.core.XGBoostError) as exc:
        warnings.warn(f"fmr_orthogonal failed: {exc}", RuntimeWarning)
        return dict.fromkeys(keys, np.nan)
