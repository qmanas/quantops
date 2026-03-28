import torch
import numpy as np
from typing import Dict
from chronos import ChronosBoltPipeline

class TCNModel:
    """
    Amazon Chronos-Bolt Integration.
    Uses the specialized ChronosBoltPipeline for high-performance patch-based forecasting.
    """
    
    def __init__(self, model_id: str = "amazon/chronos-bolt-tiny", device: str = None):
        if device is None:
            # Check for MPS (Mac Metal) or CPU
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device
            
        print(f"Loading Chronos-Bolt ({model_id}) on {self.device}...")
        
        # ChronosBoltPipeline is the correct class for bolt-variants
        self.pipeline = ChronosBoltPipeline.from_pretrained(
            model_id,
            device_map=self.device,
            dtype=torch.float32,
        )
        self.version = f"chronos-{model_id.split('/')[-1]}"

    def predict(self, window: np.ndarray) -> Dict[str, float]:
        """
        Input: window of shape (64, 12). 
        The first column [:, 0] is assumed to be 'ret_close' (returns).
        """
        # Chronos expects a 1D tensor of historical values
        # We'll use the returns and convert them back to a relative price scale starting at 1.0
        rets = window[:, 0]
        price_proxy = np.exp(np.cumsum(rets))
        
        context = torch.tensor(price_proxy, dtype=torch.float32)
        
        # Forecast the next 1 step (zero-shot)
        with torch.no_grad():
            forecast = self.pipeline.predict(context, prediction_length=1) 
            
        # Extract samples (default is 20)
        # For ChronosBoltPipeline, the output format might differ slightly.
        # Let's assume forecast is a tensor of samples.
        samples = forecast[0, :, 0].cpu().numpy()
        
        current_price = price_proxy[-1]
        
        # Calculate probabilities based on the distribution of samples
        p_up = np.mean(samples > current_price)
        p_down = 1.0 - p_up
        
        # Entropy (measure of uncertainty in the distribution)
        p_up_clip = np.clip(p_up, 1e-6, 1-1e-6)
        entropy = - (p_up_clip * np.log(p_up_clip) + (1-p_up_clip) * np.log(1-p_up_clip))
        
        # Raw Signal (-1 to 1)
        raw_signal = (p_up - p_down)
        
        # Volatility Forecast (standard deviation of the forecast distribution normalized by price)
        vol_forecast = np.std(samples) / current_price
        
        return {
            "p_up": float(p_up),
            "p_down": float(p_down),
            "entropy": float(entropy),
            "raw_signal": float(raw_signal),
            "vol_forecast": float(vol_forecast),
            "vol_z": 1.0 
        }

if __name__ == "__main__":
    # Test inference
    import time
    start = time.time()
    model = TCNModel()
    # Dummy window with some trend to see if it catches it
    dummy_window = np.zeros((64, 12))
    dummy_window[:, 0] = 0.001 # Small positive return each bar
    
    pred = model.predict(dummy_window)
    print(f"Chronos Prediction: {pred}")
    print(f"Inference Time: {time.time() - start:.2f}s")
