# Copyright (c) 2014 by Farsight Security, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Author : Avinash Lakshman (alakshman@facebook.com)
#          Prashant Malik (pmalik@facebook.com)
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import operator

import six

_min_buckets = 2
_min_K = 1
_max_int = 2**64-1

# In the following keyspaceName, the row 'i' shows false positive rates if i
# buckets per element are used.  Cell 'j' shows false positive rates if j hash
# functions are used.  The first row is 'i=0', the first column is 'j=0'.
# Each cell (i,j) the false positive rate determined by using i buckets per
# element and j hash functions.
_probs = [
    [1.0], # dummy row representing 0 buckets per element
    [1.0, 1.0], # dummy row representing 1 buckets per element
    [1.0, 0.393,  0.400],
    [1.0, 0.283,  0.237,   0.253],
    [1.0, 0.221,  0.155,   0.147,   0.160],
    [1.0, 0.181,  0.109,   0.092,   0.092,   0.101], # 5
    [1.0, 0.154,  0.0804,  0.0609,  0.0561,  0.0578,   0.0638],
    [1.0, 0.133,  0.0618,  0.0423,  0.0359,  0.0347,   0.0364],
    [1.0, 0.118,  0.0489,  0.0306,  0.024,   0.0217,   0.0216,   0.0229],
    [1.0, 0.105,  0.0397,  0.0228,  0.0166,  0.0141,   0.0133,   0.0135,   0.0145],
    [1.0, 0.0952, 0.0329,  0.0174,  0.0118,  0.00943,  0.00844,  0.00819,  0.00846], # 10
    [1.0, 0.0869, 0.0276,  0.0136,  0.00864, 0.0065,   0.00552,  0.00513,  0.00509],
    [1.0, 0.08,   0.0236,  0.0108,  0.00646, 0.00459,  0.00371,  0.00329,  0.00314],
    [1.0, 0.074,  0.0203,  0.00875, 0.00492, 0.00332,  0.00255,  0.00217,  0.00199,  0.00194],
    [1.0, 0.0689, 0.0177,  0.00718, 0.00381, 0.00244,  0.00179,  0.00146,  0.00129,  0.00121,  0.0012],
    [1.0, 0.0645, 0.0156,  0.00596, 0.003,   0.00183,  0.00128,  0.001,    0.000852, 0.000775, 0.000744], # 15
    [1.0, 0.0606, 0.0138,  0.005,   0.00239, 0.00139,  0.000935, 0.000702, 0.000574, 0.000505, 0.00047,  0.000459],
    [1.0, 0.0571, 0.0123,  0.00423, 0.00193, 0.00107,  0.000692, 0.000499, 0.000394, 0.000335, 0.000302, 0.000287, 0.000284],
    [1.0, 0.054,  0.0111,  0.00362, 0.00158, 0.000839, 0.000519, 0.00036,  0.000275, 0.000226, 0.000198, 0.000183, 0.000176],
    [1.0, 0.0513, 0.00998, 0.00312, 0.0013,  0.000663, 0.000394, 0.000264, 0.000194, 0.000155, 0.000132, 0.000118, 0.000111, 0.000109],
    [1.0, 0.0488, 0.00906, 0.0027,  0.00108, 0.00053,  0.000303, 0.000196, 0.00014,  0.000108, 8.89e-05, 7.77e-05, 7.12e-05, 6.79e-05, 6.71e-05] # 20
]  # the first column is a dummy column representing K=0.

opt_K_per_buckets = [max(1, min(enumerate(p), key=operator.itemgetter(1))[0]) for p in _probs]

def compute_bloom_spec(max_buckets_per_element, max_false_pos_prob):
    if not max_buckets_per_element > 0:
        raise ValueError('max_buckets_per_element must be greater than 0')
    if max_buckets_per_element >= len(_probs):
        raise ValueError('max_buckets_per_element must be less than {}'.format(len(_probs)))
    max_K = len(_probs[max_buckets_per_element]) - 1

    # Handle the trivial cases
    if max_false_pos_prob >= _probs[_min_buckets][_min_K]:
        return (2, opt_K_per_buckets[2])
    
    if max_false_pos_prob < _probs[max_buckets_per_element][max_K]:
        raise ValueError('Unable to satisfy {} with {} buckets per element'.format(
            max_false_pos_prob, max_buckets_per_element))

    # First find the minimal required number of buckets:
    buckets_per_element = 2
    K = opt_K_per_buckets[2]

    while _probs[buckets_per_element][K] > max_false_pos_prob:
        buckets_per_element += 1
        K = opt_K_per_buckets[buckets_per_element]

    # Now that the number of buckets is sufficient, see if we can relax K
    # without losing too much precision.
    while _probs[buckets_per_element][K - 1] <= max_false_pos_prob:
        K -= 1

    return (K, buckets_per_element)

def max_buckets_per_element(num_elements):
    num_elements = max(1, num_elements)
    v = six.MAXSIZE / float(num_elements)
    if v < 1.0:
        raise ValueError('Cannot compute probabilities for {} elements.'.format(num_elements))
    return min(len(_probs)-1, int(v))
