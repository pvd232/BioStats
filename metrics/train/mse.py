import torch


def mse(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    if x.shape != y.shape:
        raise ValueError("x and y must have the same shape")

    if x.shape[0] < 1:
        raise ValueError("Must have at least one predicted perturbation")    
    
    if x.device != y.device:
        raise ValueError("x and y must be on the same device to perform arithmetic")

    if not x.isfinite().all() or not y.isfinite().all() or x.is_complex() or y.is_complex():
        raise ValueError("x and y must be real numbers")

    res = (x - y).square().mean()
    return res