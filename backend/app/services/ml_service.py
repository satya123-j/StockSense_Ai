import time
import math
import datetime
import pytz
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from backend.app.services.stock_service import StockService
from backend.app.services.instrument_mapping_service import InstrumentMappingService
from backend.app.utils.helpers import round_num

IST = pytz.timezone('Asia/Kolkata')

# In-memory cache for ML predictions (TTL: 5 minutes)
_ML_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 300  # 5 minutes


class MLService:
    """
    Machine Learning service for StockSense AI.
    
    Provides chronological time-series preparation and regression models
    (Linear Regression and Random Forest Regressor) to forecast stock price
    movements using technical and historical price features:
      - Open
      - High
      - Low
      - Close
      - Volume
      - Previous Close
      - MA20 (20-day Simple Moving Average)
      - MA50 (50-day Simple Moving Average)
    """

    FEATURE_NAMES = [
        'Open',
        'High',
        'Low',
        'Close',
        'Volume',
        'Previous Close',
        'MA20',
        'MA50'
    ]

    @staticmethod
    def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        Prepares and cleans stock data chronologically for time-series modeling.
        Computes derivative indicators (Previous Close, MA20, MA50) and the
        prediction target (next session's Close price).
        
        Args:
            df: Raw DataFrame containing OHLCV stock history.
            
        Returns:
            Tuple of (prepared_dataframe, list_of_available_feature_columns)
        """
        if df is None or df.empty:
            raise ValueError("Input DataFrame is empty or None.")

        # Copy to avoid mutating external references
        data = df.copy()

        # Normalize column names to Titlecase
        col_map = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'date': 'Date'
        }
        data = data.rename(columns={c: col_map[c.lower()] for c in data.columns if c.lower() in col_map})

        # Ensure Date is recognized and sort strictly in chronological ascending order
        if 'Date' in data.columns:
            data['Date'] = pd.to_datetime(data['Date'])
            data = data.sort_values('Date').reset_index(drop=True)

        # Cast OHLCV columns to numeric
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')

        # Fill any missing volume with 0
        if 'Volume' in data.columns:
            data['Volume'] = data['Volume'].fillna(0)

        # Ensure Close is present
        if 'Close' not in data.columns:
            raise ValueError("Dataframe must contain 'Close' price column.")

        # 1. Previous Close: Price shifted by 1 trading session backwards
        data['Previous Close'] = data['Close'].shift(1)

        # 2. MA20: 20-period Simple Moving Average of Close
        data['MA20'] = data['Close'].rolling(window=20, min_periods=20).mean()

        # 3. MA50: 50-period Simple Moving Average of Close
        data['MA50'] = data['Close'].rolling(window=50, min_periods=50).mean()

        # 4. Target variable: Next trading session Close price (shifted by -1)
        data['Target'] = data['Close'].shift(-1)

        # Determine which expected features are available
        available_features = [f for f in MLService.FEATURE_NAMES if f in data.columns]

        return data, available_features

    @staticmethod
    def split_time_series_data(
        prepared_df: pd.DataFrame,
        feature_cols: List[str],
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Splits data chronologically without random shuffling to prevent lookahead bias.
        
        Args:
            prepared_df: Output from prepare_features()
            feature_cols: List of features to use in the feature matrix X
            test_size: Proportion of recent historical records to reserve for testing
            
        Returns:
            Dictionary containing train/test splits, latest feature row, and metadata.
        """
        if len(prepared_df) < 55:
            raise ValueError(
                f"Insufficient historical data: {len(prepared_df)} records found. "
                f"At least 55-60 trading days are required to compute MA50 and perform chronological evaluation."
            )

        # The last row contains known features for today, but its Target (tomorrow) is NaN.
        # This row is preserved as the latest inference input for the next-day forecast.
        latest_row = prepared_df.iloc[-1].copy()
        latest_features = pd.DataFrame([latest_row[feature_cols].to_dict()])

        # Check that latest features do not have NaNs in the required columns
        if latest_features.isna().any().any():
            # If MA50 is NaN on the latest row, we cannot produce a valid prediction
            missing_cols = latest_features.columns[latest_features.isna().any()].tolist()
            raise ValueError(f"Latest record has missing values for features: {missing_cols}")

        # Training/Testing dataset: rows that have both complete features AND a known Target
        complete_df = prepared_df.dropna(subset=feature_cols + ['Target']).reset_index(drop=True)

        if len(complete_df) < 30:
            raise ValueError(
                f"Insufficient complete records ({len(complete_df)} valid points). "
                f"More historical data points are needed."
            )

        # Chronological index split: earliest records for training, latest for evaluation
        n_samples = len(complete_df)
        split_idx = int(n_samples * (1 - test_size))
        
        # Ensure test set has at least 5 records
        if n_samples - split_idx < 5:
            split_idx = max(5, n_samples - 5)

        train_df = complete_df.iloc[:split_idx].copy()
        test_df = complete_df.iloc[split_idx:].copy()

        X_train = train_df[feature_cols]
        y_train = train_df['Target']

        X_test = test_df[feature_cols]
        y_test = test_df['Target']

        return {
            'X_train': X_train,
            'y_train': y_train,
            'X_test': X_test,
            'y_test': y_test,
            'train_df': train_df,
            'test_df': test_df,
            'latest_features': latest_features,
            'latest_row': latest_row,
            'split_index': split_idx,
            'train_size': len(train_df),
            'test_size': len(test_df)
        }

    @staticmethod
    def _calculate_directional_accuracy(actual_prices: np.ndarray, predicted_prices: np.ndarray, prev_prices: np.ndarray) -> float:
        """
        Calculates percentage of correct directional predictions (price up vs price down).
        """
        actual_diff = actual_prices - prev_prices
        pred_diff = predicted_prices - prev_prices
        correct_directions = (actual_diff * pred_diff) >= 0
        return float(np.mean(correct_directions) * 100) if len(correct_directions) > 0 else 0.0

    @staticmethod
    def train_linear_regression(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        latest_features: pd.DataFrame,
        test_df: pd.DataFrame,
        current_close: float
    ) -> Dict[str, Any]:
        """
        Trains and evaluates an ordinary least squares Linear Regression model.
        """
        model = LinearRegression()
        model.fit(X_train, y_train)

        # Test set evaluation
        test_preds = model.predict(X_test)
        mae = float(mean_absolute_error(y_test, test_preds))
        mse = float(mean_squared_error(y_test, test_preds))
        rmse = float(np.sqrt(mse))
        r2 = float(r2_score(y_test, test_preds))

        # Directional accuracy relative to current test day close
        dir_acc = MLService._calculate_directional_accuracy(
            actual_prices=y_test.values,
            predicted_prices=test_preds,
            prev_prices=test_df['Close'].values
        )

        # Inference: Predict next trading session close
        next_day_pred = float(model.predict(latest_features)[0])
        pred_change = round_num(next_day_pred - current_close, 2)
        pred_change_pct = round_num((pred_change / current_close) * 100, 2) if current_close else 0.0

        # Feature coefficients
        coefficients = {
            col: round_num(float(coef), 4)
            for col, coef in zip(X_train.columns, model.coef_)
        }

        return {
            'model_name': 'Linear Regression',
            'predicted_close': round_num(next_day_pred, 2),
            'current_close': round_num(current_close, 2),
            'predicted_change': pred_change,
            'predicted_change_percent': pred_change_pct,
            'direction': 'UP' if pred_change >= 0 else 'DOWN',
            'signal': 'BULLISH' if pred_change > 0.25 else ('BEARISH' if pred_change < -0.25 else 'NEUTRAL'),
            'metrics': {
                'mae': round_num(mae, 2),
                'rmse': round_num(rmse, 2),
                'mse': round_num(mse, 2),
                'r2_score': round_num(r2, 4),
                'directional_accuracy_pct': round_num(dir_acc, 2)
            },
            'intercept': round_num(float(model.intercept_), 4),
            'coefficients': coefficients,
            '_raw_test_preds': test_preds.tolist()
        }

    @staticmethod
    def train_random_forest(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        latest_features: pd.DataFrame,
        test_df: pd.DataFrame,
        current_close: float,
        n_estimators: int = 100,
        random_state: int = 42
    ) -> Dict[str, Any]:
        """
        Trains and evaluates an ensemble Random Forest Regressor.
        """
        model = RandomForestRegressor(
            n_estimators=n_estimators,
            random_state=random_state,
            max_depth=10,
            min_samples_split=4,
            min_samples_leaf=2,
            n_jobs=-1
        )
        model.fit(X_train, y_train)

        # Test set evaluation
        test_preds = model.predict(X_test)
        mae = float(mean_absolute_error(y_test, test_preds))
        mse = float(mean_squared_error(y_test, test_preds))
        rmse = float(np.sqrt(mse))
        r2 = float(r2_score(y_test, test_preds))

        # Directional accuracy relative to current test day close
        dir_acc = MLService._calculate_directional_accuracy(
            actual_prices=y_test.values,
            predicted_prices=test_preds,
            prev_prices=test_df['Close'].values
        )

        # Inference: Predict next trading session close
        next_day_pred = float(model.predict(latest_features)[0])
        pred_change = round_num(next_day_pred - current_close, 2)
        pred_change_pct = round_num((pred_change / current_close) * 100, 2) if current_close else 0.0

        # Feature importances (sorted descending)
        sorted_importances = sorted(
            zip(X_train.columns, model.feature_importances_),
            key=lambda x: x[1],
            reverse=True
        )
        feature_importances = {
            col: round_num(float(imp), 4)
            for col, imp in sorted_importances
        }

        return {
            'model_name': 'Random Forest Regressor',
            'predicted_close': round_num(next_day_pred, 2),
            'current_close': round_num(current_close, 2),
            'predicted_change': pred_change,
            'predicted_change_percent': pred_change_pct,
            'direction': 'UP' if pred_change >= 0 else 'DOWN',
            'signal': 'BULLISH' if pred_change > 0.25 else ('BEARISH' if pred_change < -0.25 else 'NEUTRAL'),
            'metrics': {
                'mae': round_num(mae, 2),
                'rmse': round_num(rmse, 2),
                'mse': round_num(mse, 2),
                'r2_score': round_num(r2, 4),
                'directional_accuracy_pct': round_num(dir_acc, 2)
            },
            'n_estimators': n_estimators,
            'feature_importances': feature_importances,
            '_raw_test_preds': test_preds.tolist()
        }

    @classmethod
    def predict_from_dataframe(
        cls,
        df: pd.DataFrame,
        symbol: str = "STOCK",
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Executes the end-to-end ML pipeline on an input DataFrame:
        1. Prepares chronological features (OHLCV, Prev Close, MA20, MA50)
        2. Splits chronologically without random shuffling
        3. Trains Linear Regression & Random Forest Regressor
        4. Calculates quantitative validation metrics
        5. Predicts next-day close and ensemble consensus
        """
        now_ist_str = datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')

        try:
            # 1. Feature Engineering
            prepared_df, feature_cols = cls.prepare_features(df)

            # 2. Chronological Split
            splits = cls.split_time_series_data(prepared_df, feature_cols, test_size=test_size)

            X_train = splits['X_train']
            y_train = splits['y_train']
            X_test = splits['X_test']
            y_test = splits['y_test']
            latest_features = splits['latest_features']
            latest_row = splits['latest_row']
            test_df = splits['test_df']

            current_close = float(latest_row['Close'])
            latest_date_str = str(latest_row.get('Date', 'N/A'))[:10]

            # 3. Model Training & Evaluation
            lr_results = cls.train_linear_regression(
                X_train=X_train,
                y_train=y_train,
                X_test=X_test,
                y_test=y_test,
                latest_features=latest_features,
                test_df=test_df,
                current_close=current_close
            )

            rf_results = cls.train_random_forest(
                X_train=X_train,
                y_train=y_train,
                X_test=X_test,
                y_test=y_test,
                latest_features=latest_features,
                test_df=test_df,
                current_close=current_close
            )

            # 4. Ensemble Consensus
            avg_predicted_close = round_num((lr_results['predicted_close'] + rf_results['predicted_close']) / 2.0, 2)
            avg_change = round_num(avg_predicted_close - current_close, 2)
            avg_change_pct = round_num((avg_change / current_close) * 100, 2) if current_close else 0.0

            ensemble = {
                'predicted_close': avg_predicted_close,
                'current_close': round_num(current_close, 2),
                'predicted_change': avg_change,
                'predicted_change_percent': avg_change_pct,
                'direction': 'UP' if avg_change >= 0 else 'DOWN',
                'signal': 'BULLISH' if avg_change > 0.25 else ('BEARISH' if avg_change < -0.25 else 'NEUTRAL')
            }

            # 5. Model Comparison
            lr_rmse = lr_results['metrics']['rmse']
            rf_rmse = rf_results['metrics']['rmse']
            lr_r2 = lr_results['metrics']['r2_score']
            rf_r2 = rf_results['metrics']['r2_score']

            best_model = "Random Forest Regressor" if (rf_rmse <= lr_rmse) else "Linear Regression"

            # 6. Recent Test Points Comparison (up to last 15 test points for inspection)
            recent_test_comparison = []
            test_dates = test_df['Date'].astype(str).str[:10].tolist() if 'Date' in test_df.columns else [f"T-{i}" for i in range(len(test_df))]
            actual_test_closes = [round_num(val, 2) for val in y_test.tolist()]
            lr_preds = [round_num(val, 2) for val in lr_results.pop('_raw_test_preds')]
            rf_preds = [round_num(val, 2) for val in rf_results.pop('_raw_test_preds')]

            tail_len = min(15, len(test_df))
            for i in range(len(test_df) - tail_len, len(test_df)):
                recent_test_comparison.append({
                    'date': test_dates[i] if i < len(test_dates) else f"Idx-{i}",
                    'actual_target_close': actual_test_closes[i],
                    'linear_regression_pred': lr_preds[i],
                    'random_forest_pred': rf_preds[i]
                })

            return {
                'status': 'success',
                'symbol': symbol,
                'timestamp': now_ist_str,
                'data_summary': {
                    'total_historical_candles': len(df),
                    'clean_records_after_indicators': len(prepared_df.dropna(subset=feature_cols)),
                    'train_samples': len(X_train),
                    'test_samples': len(X_test),
                    'features_used': feature_cols,
                    'latest_candle_date': latest_date_str,
                    'current_close': round_num(current_close, 2)
                },
                'predictions': {
                    'linear_regression': lr_results,
                    'random_forest': rf_results,
                    'ensemble': ensemble
                },
                'comparison': {
                    'best_model_by_rmse': best_model,
                    'rmse_delta': round_num(abs(lr_rmse - rf_rmse), 2),
                    'best_model_by_r2': "Random Forest Regressor" if (rf_r2 >= lr_r2) else "Linear Regression"
                },
                'recent_test_series': recent_test_comparison
            }

        except Exception as e:
            return {
                'status': 'error',
                'symbol': symbol,
                'timestamp': now_ist_str,
                'message': str(e),
                'error_type': type(e).__name__
            }

    @classmethod
    def predict(
        cls,
        symbol: str,
        period: str = '1y',
        test_size: float = 0.2,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        High-level prediction method:
        Fetches existing historical stock candles from StockSense AI StockService
        and executes the ML training and prediction pipeline.
        
        Args:
            symbol: NSE/BSE stock ticker (e.g. 'TCS', 'RELIANCE', 'INFY')
            period: History lookback period (default '1y' to ensure adequate moving average data)
            test_size: Proportion of recent historical sessions reserved for out-of-sample testing
            use_cache: Whether to read from/write to in-memory prediction cache
            
        Returns:
            JSON-serializable prediction results dictionary.
        """
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol)
        cache_key = f"ML_{clean_symbol}_{period.lower()}_{test_size}"
        now = time.time()

        if use_cache and cache_key in _ML_CACHE:
            entry = _ML_CACHE[cache_key]
            if (now - entry['timestamp']) < CACHE_TTL:
                return entry['data']

        # Fetch historical data using existing StockService
        history = StockService.get_stock_history(clean_symbol, range_period=period, interval='1d')
        points = history.get('points', []) if history else []

        if not points or len(points) == 0:
            return {
                'status': 'error',
                'symbol': clean_symbol,
                'message': f"No historical candle data could be retrieved for '{clean_symbol}' (period: {period}).",
                'timestamp': datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')
            }

        # Convert candle list of dicts to DataFrame
        df = pd.DataFrame(points)

        # Run pipeline
        results = cls.predict_from_dataframe(df, symbol=clean_symbol, test_size=test_size)

        if results.get('status') == 'success' and use_cache:
            _ML_CACHE[cache_key] = {'data': results, 'timestamp': now}

        return results
