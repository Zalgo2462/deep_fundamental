from typing import Tuple, Dict

import torch

from .imips import ImipLoss


class OHNMClassicImipLoss(ImipLoss):

    def __init__(self, epsilon: float = 1e-4):
        super(OHNMClassicImipLoss, self).__init__()
        self._epsilon = torch.nn.Parameter(torch.tensor([epsilon]), requires_grad=False)

    @property
    def needs_correspondence_outputs(self) -> bool:
        return True

    @staticmethod
    def _add_if_not_none(x, y):
        return x + y if y is not None else x

    @staticmethod
    def _detach_if_not_none(x):
        return x.detach() if x is not None else None

    def forward_with_log_data(self, maximizer_outputs: torch.Tensor, correspondence_outputs: torch.Tensor,
                              inlier_labels: torch.Tensor, outlier_labels: torch.Tensor) -> Tuple[
        torch.Tensor, Dict[str, torch.Tensor]]:
        # maximizer_outputs: BxCx1x1 where B == C
        # correspondence_outputs: BxCx1x1 where B == C
        # If h and w are not 1 w.r.t. maximizer_outpus and correspondence_outputs,
        # the center values will be extracted.

        assert (maximizer_outputs.shape[0] % maximizer_outputs.shape[1] == 0)
        assert (maximizer_outputs.shape[2] == maximizer_outputs.shape[3])

        if maximizer_outputs.shape[2] != 1:
            center_px = (maximizer_outputs.shape[2] - 1) // 2
            maximizer_outputs = maximizer_outputs[:, :, center_px, center_px]
        if correspondence_outputs.shape[2] != 1:
            center_px = (correspondence_outputs.shape[2] - 1) // 2
            correspondence_outputs = correspondence_outputs[:, :, center_px, center_px]

        maximizer_outputs = torch.sigmoid(maximizer_outputs.squeeze())  # BxCx1x1 -> BxC
        correspondence_outputs = torch.sigmoid(correspondence_outputs.squeeze())  # BxCx1x1 -> BxC

        # convert the label types so we can use torch.diag() on the labels
        if inlier_labels.dtype == torch.bool:
            inlier_labels = inlier_labels.to(torch.uint8)

        if outlier_labels.dtype == torch.bool:
            outlier_labels = outlier_labels.to(torch.uint8)

        corr_outlier_index_2d = torch.diag(outlier_labels)

        aligned_outlier_corr_outputs = correspondence_outputs[corr_outlier_index_2d]
        if aligned_outlier_corr_outputs.numel() == 0:
            outlier_correspondence_loss = None
        else:
            outlier_correspondence_loss = torch.sum(-1 * torch.log(
                torch.max(aligned_outlier_corr_outputs, self._epsilon)))

        # expand inlier_labels by num_patches_per_channel
        # inlier should begin every segment of (num patches per channel)
        num_patches_per_channel = maximizer_outputs.shape[0] // maximizer_outputs.shape[1]

        expanded_inlier_labels = torch.zeros(
            inlier_labels.shape[0] * num_patches_per_channel,
            dtype=torch.uint8, device=inlier_labels.device
        )
        maximum_patch_index = torch.arange(0, maximizer_outputs.shape[0], num_patches_per_channel)
        expanded_inlier_labels[maximum_patch_index] = inlier_labels

        has_data_labels = inlier_labels | outlier_labels  # B
        expanded_outlier_labels = (has_data_labels.repeat_interleave(num_patches_per_channel) &
                                   torch.logical_not(expanded_inlier_labels).to(dtype=torch.uint8))

        maxima_inlier_index_2d = expanded_inlier_labels[:, None] * torch.repeat_interleave(
            torch.eye(maximizer_outputs.shape[1], device=maximizer_outputs.device, dtype=torch.uint8),
            num_patches_per_channel, dim=0
        )

        maxima_outlier_index_2d = expanded_outlier_labels[:, None] * torch.repeat_interleave(
            torch.eye(maximizer_outputs.shape[1], device=maximizer_outputs.device, dtype=torch.uint8),
            num_patches_per_channel, dim=0
        )

        if maxima_outlier_index_2d.sum() == 0:
            outlier_maximizer_loss = None
        else:
            num_outliers_per_channel = maxima_outlier_index_2d.sum(dim=0).clamp_min(1.0)
            outlier_maximizer_scores = -1 * torch.log(
                torch.max(-1 * maximizer_outputs + 1, self._epsilon))
            outlier_maximizer_loss = (
                    (outlier_maximizer_scores * maxima_outlier_index_2d).sum(dim=0) / num_outliers_per_channel
            ).sum()

        aligned_inlier_maximizer_scores = maximizer_outputs[maxima_inlier_index_2d]
        if aligned_inlier_maximizer_scores.numel() == 0:
            inlier_loss = None
        else:
            inlier_loss = torch.sum(-1 * torch.log(
                torch.max(aligned_inlier_maximizer_scores, self._epsilon)))

        # Finally, if a channel attains its maximum response inside of a given radius
        # about it's target correspondence site, the responses of all the other channels
        # to it's maximizing patch are minimized.

        maximizer_outputs = maximizer_outputs[maximum_patch_index]  # BxC where B==C
        # equivalent: inlier_labels.unsqueeze(1).repeat(1, inlier_labels.shape[0]) - inlier_labels.diag()
        unaligned_inlier_index = torch.diag(inlier_labels) ^ inlier_labels.unsqueeze(1)
        unaligned_inlier_maximizer_scores = maximizer_outputs[unaligned_inlier_index]
        unaligned_maximizer_loss = torch.sum(unaligned_inlier_maximizer_scores)
        if unaligned_inlier_maximizer_scores.nelement() == 0:
            unaligned_maximizer_loss = torch.zeros([1], requires_grad=True, device=unaligned_maximizer_loss.device)

        total_loss = torch.zeros(1, device=maximizer_outputs.device, dtype=maximizer_outputs.dtype, requires_grad=True)

        # imips just adds the unaligned scores to the loss directly
        total_loss = self._add_if_not_none(total_loss, outlier_correspondence_loss)
        total_loss = self._add_if_not_none(total_loss, outlier_maximizer_loss)
        total_loss = self._add_if_not_none(total_loss, inlier_loss)
        total_loss = self._add_if_not_none(total_loss, unaligned_maximizer_loss)

        return total_loss, {
            "loss": total_loss.detach(),
            "outlier_correspondence_loss": self._detach_if_not_none(outlier_correspondence_loss),
            "outlier_maximizer_loss": self._detach_if_not_none(outlier_maximizer_loss),
            "inlier_maximizer_loss": self._detach_if_not_none(inlier_loss),
            "unaligned_maximizer_loss": self._detach_if_not_none(unaligned_maximizer_loss),
        }
