import math
import numpy as np

import torch
import torch.nn.init as init
from torch.nn import Module, Parameter
import torch.nn.functional as F
from torch.nn.modules.utils import _pair

from .utils import MulExpAddFunction

class _BayesConvNdMF(Module):
    r"""
    Applies Bayesian Convolution
    """
    __constants__ = ['stride', 'padding', 'dilation',
                     'groups', 'bias', 'in_channels',
                     'out_channels', 'kernel_size']

    def __init__(self, in_channels, out_channels, kernel_size, stride,
                 padding, dilation, groups, bias):
        super(_BayesConvNdMF, self).__init__()
        if in_channels % groups != 0:
            raise ValueError('in_channels must be divisible by groups')
        if out_channels % groups != 0:
            raise ValueError('out_channels must be divisible by groups')
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        if isinstance(self.kernel_size, int):
            self.kernel_size = (self.kernel_size, self.kernel_size)
        self.stride = stride
        self.padding = padding
        self.dilation = dilation
        self.groups = groups

        self.weight_mu = Parameter(torch.Tensor(
            out_channels, in_channels // groups, *self.kernel_size))
        self.weight_psi = Parameter(torch.Tensor(
            out_channels, in_channels // groups, *self.kernel_size))

        if bias is None or bias is False :
            self.bias = False
        else:
            self.bias = True

        if self.bias:
            self.bias_mu = Parameter(torch.Tensor(out_channels))
            self.bias_psi = Parameter(torch.Tensor(out_channels))
        else:
            self.register_parameter('bias_mu', None)
            self.register_parameter('bias_psi', None)
        self.reset_parameters()

    def reset_parameters(self):
        n = self.in_channels
        n *= np.prod(list(self.kernel_size))
        stdv = 1.0 / math.sqrt(n)
        self.weight_mu.data.uniform_(-stdv, stdv)
        self.weight_psi.data.uniform_(-6, -5)

        if self.bias :
            self.bias_mu.data.uniform_(-stdv, stdv)
            self.bias_psi.data.uniform_(-6, -5)

    def extra_repr(self):
        s = ('{in_channels}, {out_channels}, kernel_size={kernel_size}'
             ', stride={stride}')
        s += ', padding={padding}'
        s += ', dilation={dilation}'
        s += ', groups={groups}'
        s += ', bias=False'
        return s.format(**self.__dict__)

    def __setstate__(self, state):
        super(_BayesConvNdMF, self).__setstate__(state)

class BayesConv2dMF(_BayesConvNdMF):
    r"""
    Applies Bayesian Convolution for 2D inputs
    """
    def __init__(self, in_channels, out_channels, kernel_size, stride=1,
                 padding=0, dilation=1, groups=1, bias=False,
                 deterministic=False, num_mc_samples=None):
        super(BayesConv2dMF, self).__init__(
            in_channels, out_channels, kernel_size, stride,
            padding, dilation, groups, bias)
        self.deterministic = deterministic
        self.num_mc_samples = num_mc_samples
        self.parallel_eval = False
        self.weight_size = list(self.weight_mu.shape)
        self.bias_size = list(self.bias_mu.shape) if self.bias else None
        self.mul_exp_add = MulExpAddFunction.apply

        self.local_reparam = False
        self.flipout = False
        self.single_eps = False

    def forward(self, input):
        r"""
        Overriden.
        """
        if self.deterministic:
            out = F.conv2d(input, weight=self.weight_mu, bias=self.bias_mu,
                            stride=self.stride, dilation=self.dilation,
                            groups=self.groups, padding=self.padding)
        elif not self.parallel_eval:
            if self.single_eps:
                assert not self.bias
                weight = torch.randn_like(self.weight_mu).mul_(self.weight_psi.exp()).add_(self.weight_mu)
                out = F.conv2d(input, weight=weight, bias=None,
                                stride=self.stride, dilation=self.dilation,
                                groups=self.groups, padding=self.padding)
            elif self.local_reparam:
                assert not self.bias
                act_mu = F.conv2d(input, weight=self.weight_mu, bias=None,
                                  stride=self.stride, padding=self.padding,
                                  dilation=self.dilation, groups=self.groups)
                act_var = F.conv2d(input**2,
                                  weight=(self.weight_psi*2).exp_(), bias=None,
                                  stride=self.stride, padding=self.padding,
                                  dilation=self.dilation, groups=self.groups)
                act_std = act_var.clamp(1e-8).sqrt_()
                # print(act_std.data.norm().item())
                out =  torch.randn_like(act_mu).mul_(act_std).add_(act_mu)
            elif self.flipout:
                assert not self.bias
                outputs = F.conv2d(input, weight=self.weight_mu, bias=None,
                                   stride=self.stride, padding=self.padding,
                                   dilation=self.dilation, groups=self.groups)

                # sampling perturbation signs
                sign_input = torch.empty(input.size(0), input.size(1), 1, 1, device=input.device).uniform_(-1, 1).sign()
                sign_output = torch.empty(outputs.size(0), outputs.size(1), 1, 1, device=input.device).uniform_(-1, 1).sign()

                # gettin perturbation weights
                delta_kernel = torch.randn_like(self.weight_psi) * torch.exp(self.weight_psi)

                # perturbed feedforward
                perturbed_outputs = F.conv2d(input * sign_input,
                                             weight=delta_kernel,
                                             bias=None,
                                             stride=self.stride,
                                             padding=self.padding,
                                             dilation=self.dilation,
                                             groups=self.groups)
                out = outputs + perturbed_outputs * sign_output
            else:
                bs = input.shape[0]
                weight = self.mul_exp_add(torch.empty(bs, *self.weight_size,
                                                      device=input.device,
                                                      dtype=input.dtype).normal_(0, 1),
                                          self.weight_psi, self.weight_mu).view(
                                    bs*self.weight_size[0], *self.weight_size[1:])
                out = F.conv2d(input.view(1, -1, input.shape[2], input.shape[3]),
                               weight=weight, bias=None,
                               stride=self.stride, dilation=self.dilation,
                               groups=self.groups*bs, padding=self.padding)
                out = out.view(bs, self.out_channels, out.shape[2], out.shape[3])

                if self.bias:
                    bias = self.mul_exp_add(torch.empty(bs, *self.bias_size,
                                                        device=input.device,
                                                        dtype=input.dtype).normal_(0, 1),
                                            self.bias_psi, self.bias_mu)
                    out = out + bias[:, :, None, None]
        else:
            if input.dim() == 4:
                input = input.unsqueeze(1).repeat(1, self.num_mc_samples, 1, 1, 1)

            weight = self.mul_exp_add(torch.empty(self.num_mc_samples,
                                                  *self.weight_size,
                                                  device=input.device,
                                                  dtype=input.dtype).normal_(0, 1),
                                      self.weight_psi, self.weight_mu).view(
                self.num_mc_samples*self.weight_size[0], *self.weight_size[1:])
            out = F.conv2d(input.flatten(start_dim=1, end_dim=2),
                           weight=weight, bias=None,
                           stride=self.stride, dilation=self.dilation,
                           groups=self.groups*self.num_mc_samples,
                           padding=self.padding)
            out = out.view(out.shape[0], self.num_mc_samples,
                           self.out_channels, out.shape[2], out.shape[3])
            if self.bias:
                bias = self.mul_exp_add(torch.empty(self.num_mc_samples,
                                                    *self.bias_size,
                                                    device=input.device,
                                                    dtype=input.dtype).normal_(0, 1),
                                        self.bias_psi, self.bias_mu)
                out = out + bias[None, :, :, None, None]
        return out
