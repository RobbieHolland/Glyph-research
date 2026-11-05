"""Original MHG unadjusted fit, without model/data-loader imports."""
from types import SimpleNamespace
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.stats import norm

class IsolatedModel:
    def __init__(self,seed=42):
        self.config=SimpleNamespace(seed=seed)

    def fit_isolated_model(self, standardized_feature_values, outcome_values):
        # Ensure correct shape
        if standardized_feature_values.ndim == 1:
            standardized_feature_values = standardized_feature_values[:, None]

        # 1. Your specific model (KEPT EXACTLY AS REQUESTED)
        model = LogisticRegression(max_iter=1000, random_state=self.config.seed, penalty=None)
        model.fit(standardized_feature_values, outcome_values)
        
        # 2. Extract Coefs and Probs
        coef = model.coef_[0][0]
        pred_probs = model.predict_proba(standardized_feature_values)[:, 1]
        
        try:
            # 3. Calculate Hessian (Fisher Information)
            # The weights 'w' are p * (1-p) for Logistic Regression
            w = pred_probs * (1 - pred_probs)
            
            # Add intercept column for matrix math (sklearn adds it implicitly, so we must too)
            X_design = np.column_stack([np.ones(standardized_feature_values.shape[0]), standardized_feature_values])
            
            # Fisher Info = X.T * W * X
            fisher_info = X_design.T @ (X_design * w[:, None])

            # 4. Invert Hessian to get Covariance Matrix
            # USE PINV (Pseudo-Inverse) instead of inv + try/except. 
            # It automatically handles cases where features are correlated or singular.
            cov_matrix = np.linalg.pinv(fisher_info)
            
            # Diagonal elements are variances. 
            # Index [1,1] corresponds to the feature (Index [0,0] is intercept)
            var_coef = cov_matrix[1, 1]
            se = np.sqrt(var_coef)

            # 5. Standard Stats Logic
            z_score = coef / se
            p_value = 2 * norm.sf(np.abs(z_score)) # Two-tailed p-value
            
            z_critical = 1.96 # Approx for 95% CI
            coef_ci_lower = coef - z_critical * se
            coef_ci_upper = coef + z_critical * se
        except Exception as e:
            coef_ci_lower = None
            coef_ci_upper = None
            p_value = None
            print(f"Error computing isolated model statistics: {e}")

        return {
            'isolated_odds_ratio': np.exp(coef),
            'isolated_auc': roc_auc_score(outcome_values, pred_probs),
            'isolated_odds_ratio_ci_lower': np.exp(coef_ci_lower),
            'isolated_odds_ratio_ci_upper': np.exp(coef_ci_upper),
            'isolated_odds_ratio_p_value': p_value,
        }
