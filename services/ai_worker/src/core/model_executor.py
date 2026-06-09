"""
AI Model Executor

Handles loading and executing AI models with support for:
- Local model storage (filesystem-based)
- GPU/CPU device detection and management
- Model versioning and metadata
- Error handling and validation
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Model metadata and configuration"""
    model_id: str
    version: str
    framework: str  # pytorch, tensorflow, sklearn, etc.
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    gpu_required: bool = False
    expected_latency_ms: Optional[float] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of model execution"""
    output: Dict[str, Any]
    metadata: Dict[str, Any]
    execution_time_ms: float
    device_used: str
    model_version: str


class ModelExecutor:
    """
    Executes AI models loaded from local filesystem.
    
    Directory structure:
        models/
        ├── sentiment_v1.0/
        │   ├── weights.bin (or model.pt, model.pb, etc)
        │   ├── config.json
        │   └── metadata.json
        └── sentiment_v1.1/
            ├── weights.bin
            ├── config.json
            └── metadata.json
    """
    
    def __init__(self, model_base_path: str, enable_gpu: bool = True):
        """
        Initialize Model Executor
        
        Args:
            model_base_path: Base directory where models are stored
            enable_gpu: Whether to attempt GPU usage
        """
        self.model_base_path = Path(model_base_path)
        self.enable_gpu = enable_gpu
        self.loaded_models: Dict[str, Any] = {}
        self.model_metadata: Dict[str, ModelMetadata] = {}
        self.device = self._detect_device()
        
        logger.info(f"ModelExecutor initialized with base path: {self.model_base_path}")
        logger.info(f"Device detected: {self.device}, GPU enabled: {enable_gpu}")
        
        # Ensure model directory exists
        self.model_base_path.mkdir(parents=True, exist_ok=True)
    
    def _detect_device(self) -> str:
        """
        Detect available device for model execution
        
        Returns:
            String identifier: 'cuda', 'mps' (Apple Silicon), or 'cpu'
        """
        try:
            import torch
            if self.enable_gpu:
                if torch.cuda.is_available():
                    device = 'cuda'
                    logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    device = 'mps'
                    logger.info("Apple Metal Performance Shaders (MPS) available")
                else:
                    device = 'cpu'
            else:
                device = 'cpu'
        except ImportError:
            logger.warning("PyTorch not available, defaulting to CPU")
            device = 'cpu'
        except Exception as e:
            logger.warning(f"Error detecting GPU: {e}, falling back to CPU")
            device = 'cpu'
        
        return device
    
    def list_available_models(self) -> Dict[str, list]:
        """
        List all available models in the model directory
        
        Returns:
            Dict mapping model_id to list of versions
        """
        available = {}
        
        if not self.model_base_path.exists():
            return available
        
        for model_dir in self.model_base_path.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith('.'):
                model_id = model_dir.name.rsplit('_v', 1)[0]  # Extract model_id from "model_vX.Y"
                version = model_dir.name.rsplit('_v', 1)[-1] if '_v' in model_dir.name else '1.0'
                
                if model_id not in available:
                    available[model_id] = []
                available[model_id].append(version)
        
        return available
    
    def load_model(self, model_id: str, version: str = "1.0") -> bool:
        """
        Load a model from filesystem
        
        Args:
            model_id: Model identifier (e.g., 'sentiment')
            version: Model version (e.g., '1.0')
            
        Returns:
            True if successful, False otherwise
        """
        model_key = f"{model_id}::{version}"
        
        # Return if already loaded
        if model_key in self.loaded_models:
            logger.debug(f"Model {model_key} already loaded")
            return True
        
        model_path = self.model_base_path / f"{model_id}_v{version}"
        
        if not model_path.exists():
            logger.error(f"Model path does not exist: {model_path}")
            return False
        
        try:
            # Load metadata
            metadata_path = model_path / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata_dict = json.load(f)
                    self.model_metadata[model_key] = ModelMetadata(**metadata_dict)
            else:
                logger.warning(f"No metadata.json found for {model_key}")
                self.model_metadata[model_key] = ModelMetadata(
                    model_id=model_id,
                    version=version,
                    framework="unknown",
                    input_schema={},
                    output_schema={}
                )
            
            # Load model based on framework
            config_path = model_path / "config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    framework = config.get('framework', 'pytorch')
            else:
                framework = self.model_metadata[model_key].framework or 'pytorch'
            
            # Load model file (try common names)
            model_file = None
            for filename in ["model.pt", "model.bin", "model.pkl", "weights.bin"]:
                candidate = model_path / filename
                if candidate.exists():
                    model_file = candidate
                    break
            
            if not model_file:
                logger.warning(f"No model file found in {model_path}")
                # Still mark as "loaded" for placeholder execution
                self.loaded_models[model_key] = {"placeholder": True, "path": str(model_path)}
                logger.info(f"Placeholder model registered for {model_key}")
                return True
            
            # Actual model loading (framework-specific)
            try:
                if framework == 'pytorch':
                    import torch
                    model = torch.load(model_file, map_location=self.device)
                    model.eval()  # Set to evaluation mode
                    self.loaded_models[model_key] = model
                    logger.info(f"PyTorch model loaded: {model_key} on device {self.device}")
                
                elif framework == 'tensorflow':
                    try:
                        import tensorflow as tf
                        model = tf.keras.models.load_model(str(model_file))
                        self.loaded_models[model_key] = model
                        logger.info(f"TensorFlow model loaded: {model_key}")
                    except ImportError:
                        logger.warning("TensorFlow not available, storing as placeholder")
                        self.loaded_models[model_key] = {"placeholder": True, "path": str(model_path)}
                
                elif framework == 'sklearn':
                    import pickle
                    with open(model_file, 'rb') as f:
                        model = pickle.load(f)
                    self.loaded_models[model_key] = model
                    logger.info(f"scikit-learn model loaded: {model_key}")
                
                else:
                    logger.warning(f"Unknown framework: {framework}, storing as placeholder")
                    self.loaded_models[model_key] = {"placeholder": True, "path": str(model_path)}
            
            except Exception as e:
                logger.error(f"Error loading model with framework {framework}: {e}")
                # Fallback to placeholder
                self.loaded_models[model_key] = {"placeholder": True, "path": str(model_path), "error": str(e)}
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to load model {model_key}: {e}")
            return False
    
    def execute(self, model_id: str, input_data: Dict[str, Any], 
                model_version: str = "1.0") -> ExecutionResult:
        """
        Execute model inference
        
        Args:
            model_id: Model identifier
            input_data: Input data for the model
            model_version: Model version to use
            
        Returns:
            ExecutionResult with output, metadata, and timing
            
        Raises:
            ValueError: If model not found or execution fails
        """
        import time
        
        model_key = f"{model_id}::{model_version}"
        start_time = time.time()
        
        try:
            # Load model if not already loaded
            if model_key not in self.loaded_models:
                if not self.load_model(model_id, model_version):
                    raise ValueError(f"Failed to load model {model_key}")
            
            model = self.loaded_models[model_key]
            
            # Handle placeholder models (for testing/MVP)
            if isinstance(model, dict) and model.get("placeholder"):
                logger.info(f"Using placeholder execution for {model_key}")
                output = {
                    "predictions": [],
                    "confidence": None,
                    "status": "placeholder",
                    "message": "Placeholder execution - model file not available or framework not supported"
                }
            else:
                # Real model execution
                output = self._execute_model(model, input_data)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return ExecutionResult(
                output=output,
                metadata={
                    "model_id": model_id,
                    "model_version": model_version,
                    "framework": self.model_metadata.get(model_key, ModelMetadata(
                        model_id=model_id, version=model_version, framework="unknown",
                        input_schema={}, output_schema={}
                    )).framework,
                    "device": self.device,
                    "timestamp": datetime.utcnow().isoformat()
                },
                execution_time_ms=execution_time_ms,
                device_used=self.device,
                model_version=model_version
            )
        
        except Exception as e:
            logger.error(f"Model execution failed for {model_key}: {e}")
            raise
    
    def _execute_model(self, model: Any, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute model inference (framework-agnostic wrapper)
        
        Args:
            model: Loaded model object
            input_data: Input data dictionary
            
        Returns:
            Model output as dictionary
        """
        try:
            import torch
            # PyTorch model inference
            if hasattr(model, 'forward') or hasattr(model, '__call__'):
                with torch.no_grad():
                    # Convert input_data to tensors
                    input_tensor = torch.FloatTensor(input_data.get("input", []))
                    if self.device != 'cpu':
                        input_tensor = input_tensor.to(self.device)
                    
                    output_tensor = model(input_tensor)
                    
                    # Convert output back to numpy/dict
                    if isinstance(output_tensor, torch.Tensor):
                        output = output_tensor.cpu().numpy().tolist()
                    else:
                        output = output_tensor
                    
                    return {
                        "predictions": output,
                        "confidence": None,
                        "status": "success"
                    }
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"PyTorch execution failed: {e}")
        
        try:
            import tensorflow as tf
            # TensorFlow model inference
            if hasattr(model, 'predict'):
                import numpy as np
                input_array = np.array(input_data.get("input", []))
                output = model.predict(input_array)
                return {
                    "predictions": output.tolist(),
                    "confidence": None,
                    "status": "success"
                }
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"TensorFlow execution failed: {e}")
        
        try:
            # scikit-learn model inference
            if hasattr(model, 'predict'):
                import numpy as np
                input_array = np.array(input_data.get("input", []))
                output = model.predict(input_array)
                return {
                    "predictions": output.tolist(),
                    "confidence": None,
                    "status": "success"
                }
        except Exception as e:
            logger.debug(f"scikit-learn execution failed: {e}")
        
        # Fallback: return input as-is
        logger.warning("Could not determine model type, returning input as output")
        return {
            "predictions": input_data,
            "confidence": None,
            "status": "fallback"
        }
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get information about the execution device"""
        info = {
            "device": self.device,
            "gpu_enabled": self.enable_gpu
        }
        
        try:
            import torch
            if self.device == 'cuda':
                info["cuda_device_count"] = torch.cuda.device_count()
                info["cuda_device_name"] = torch.cuda.get_device_name(0)
                info["cuda_memory_allocated_mb"] = torch.cuda.memory_allocated() / 1024 / 1024
                info["cuda_memory_reserved_mb"] = torch.cuda.memory_reserved() / 1024 / 1024
        except ImportError:
            pass
        
        return info
