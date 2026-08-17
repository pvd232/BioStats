import torch


def pearson_corr(x: torch.Tensor, y: torch.Tensor, dim: int = -1) -> torch.Tensor:
    """Return the Pearson correlation between two tensors"""

    if x.shape != y.shape:
        raise ValueError("x and y must be the same shape")

    if x.ndim == 0 or x.shape[dim] < 2:
        raise ValueError("Pearson correlation requires at least two observations")
    
    if x.device != y.device:
        raise ValueError("x and y must be on the same device to perform arithmetic")

    if not x.isfinite().all() or not y.isfinite().all() or x.is_complex() or y.is_complex():
        raise ValueError("x and y must be real numbers")

    x, y = x.to(torch.float64), y.to(torch.float64) 

    x_centered, y_centered = x - x.mean(dim = dim, keepdim=True), y - y.mean(dim=dim, keepdim=True)
    numerator = torch.linalg.vecdot(x_centered, y_centered, dim=dim) 
    # equivalent to element-wise tensor multiplication with reduction (summation) along the specified dim=i axis
    
    x_ss, y_ss = torch.sum(x_centered * x_centered, dim=dim), torch.sum(y_centered * y_centered, dim=dim)

    # x_ss.shape = (x.shape[0],) = (P,)
    if torch.any(x_ss == 0) or torch.any(y_ss == 0):
        raise ValueError("Pearson correlation is undefined for a constant vector")

    denominator = (x_ss * y_ss).sqrt()
    correlation = (numerator / denominator).clamp(-1,1)
    return correlation

    