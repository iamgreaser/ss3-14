#!/usr/bin/env python2 --
# -*- coding: utf-8 -*-

"""

Space Station 3-14
A Space Station 13 clone written for a real platform

Copyright (C) 2012, Abendsfrühstücken.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of Abendsfrühstücken nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL ABENDSFRÜHSTÜCKEN BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

from const import *

def get_gradient(v, l, h):
	iv = v
	v = max(l, min(h, v))
	v = (v-l)/(h-l)
	v = (v*(len(VIS_GRADIENT)-1)+0.5)
	fv = v
	v = int(v)
	assert v >= 0 and v < len(VIS_GRADIENT), "%i %s %s %s %s" % (v, iv, fv, l, h)
	return VIS_GRADIENT[v]

def get_twogradient(v, l, m, h):
	if v < m:
		return get_gradient(v, l, m)
	else:
		return get_gradient(-v, -h, -m)


