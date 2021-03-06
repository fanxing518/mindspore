# Copyright 2019 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
from mindspore import context
import mindspore.nn as nn
from mindspore.ops import operations as P
from mindspore import Tensor
from tests.ut.python.ops.test_math_ops import VirtualLoss
import mindspore as ms
from mindspore.common.api import _executor
from mindspore.ops import composite as C



class NetWithLoss(nn.Cell):
    def __init__(self, network):
        super(NetWithLoss, self).__init__()
        self.loss = VirtualLoss()
        self.network = network

    def construct(self, x, w1, w2):
        predict = self.network(x, w1, w2)
        return self.loss(predict)


class GradWrap(nn.Cell):
    def __init__(self, network):
        super(GradWrap, self).__init__()
        self.network = network

    def construct(self, x, w1, w2):
        return C.grad_all(self.network)(x, w1, w2)


class NetConv(nn.Cell):
    def __init__(self,
                 cin,
                 cout,
                 kernel_size,
                 stride=1,
                 pad_mode='pad',
                 padding=0,
                 dilation=1,
                 group=1,
                 has_bias=False,
                 weight_init='normal',
                 bias_init='zeros',
                 strategy=None):
        super(NetConv, self).__init__()
        self.conv = nn.Conv2d(cin,
                              cout,
                              kernel_size,
                              stride,
                              pad_mode,
                              padding,
                              dilation,
                              group,
                              has_bias,
                              weight_init,
                              bias_init)
        self.conv.conv2d.set_strategy(strategy)

    def construct(self, input_x):
        return self.conv(input_x)


def test_batch():
    class Net(nn.Cell):
        def __init__(self, strategy1, strategy2, strategy3):
            super().__init__()
            self.conv1 = NetConv(16, 8, (3, 3), bias_init='zeros', strategy=strategy1)
            self.mul1 = P.Mul().set_strategy(strategy2)
            self.conv2 = NetConv(8, 64, (9, 9), bias_init='zeros', strategy=strategy1)
            self.mul2 = P.Mul().set_strategy(strategy3)

        def construct(self, x, w1, w2):
            out1 = self.conv1(x)
            out2 = self.mul1(out1, w1)
            out3 = self.conv2(out2)
            out4 = self.mul2(out3, w2)

            return out4

    context.set_auto_parallel_context(device_num=8, global_rank=0)
    strategy1 = ((8, 1, 1, 1), (1, 1, 1, 1))
    strategy2 = ((1, 1, 1, 8), (1, 1, 1, 8))
    strategy3 = ((4, 1, 1, 2), (4, 1, 1, 2))

    net = GradWrap(NetWithLoss(Net(strategy1, strategy2, strategy3)))
    context.set_auto_parallel_context(parallel_mode="semi_auto_parallel")

    x = Tensor(np.ones([128, 16, 34, 34]), dtype=ms.float32)
    w1 = Tensor(np.ones([128, 8, 32, 32]), dtype=ms.float32)
    w2 = Tensor(np.ones([128, 64, 24, 24]), dtype=ms.float32)
    _executor.compile(net, x, w1, w2)


if __name__ == '__main__':
    test_batch()
