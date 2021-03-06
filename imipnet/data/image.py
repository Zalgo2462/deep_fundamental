import numpy as np
import torch


def load_image_for_torch(image: np.ndarray, device="cpu", requires_grad=False, dtype=torch.float32) -> torch.Tensor:
    tensor_image = torch.tensor(image, device=device, dtype=dtype, requires_grad=requires_grad)
    # Add a singleton channel dimension if the image is monochromatic
    if len(tensor_image.shape) == 2:
        tensor_image = tensor_image.unsqueeze(0)
    # Convert HxWxC images into CxHxW
    elif len(tensor_image.shape) == 3:
        tensor_image = tensor_image.permute((2, 0, 1))
    return tensor_image
