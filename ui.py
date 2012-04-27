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
import common

class EditFailureException(Exception):
	pass

class Editable:
	def __init__(self, ws, x, y, v):
		self.ws = ws
		self.x = x
		self.y = y
		self.set_value(v)
	
	def set_value(self, v):
		self.v = v
	
	def get_value(self):
		return self.v
	
	def draw(self):
		pass
	
	def edit_key_normal(self, k):
		pass
	
	def edit_key_special(self, k):
		pass
	
	def edit_focus(self):
		pass

class StringEditable(Editable):
	curx = 0
	camx = 0
	width = 30
	
	def get_value(self):
		try:
			return self.string_parse(self.v)
		except Exception, e:
			raise EditFailureException(e)
	
	def string_parse(self, v):
		return v
	
	def draw(self):
		if self.curx < self.camx:
			self.camx = self.curx
		if self.curx >= self.camx+self.width:
			self.camx = self.curx-(self.width-1)
		self.ws.addstr(self.y, self.x, self.v[self.camx:self.camx+self.width])
		self.ws.addstr(self.y, self.x+self.curx, "")
	
	def edit_key_normal(self, k):
		self.v = self.v[:self.curx] + k + self.v[self.curx:]
	
	def edit_key_special(self, k):
		if k == "backspace":
			if self.curx > 0:
				self.v = self.v[:self.curx-1] + self.v[self.curx:]
		elif k == "delete":
			if self.curx < len(self.v):
				self.v = self.v[:self.curx] + self.v[self.curx+1:]
		elif k == "left":
			self.curx = max(0, self.curx-1)
		elif k == "right":
			self.curx = min(len(self.v), self.curx)

class FloatEditable(StringEditable):
	def set_value(self, v):
		self.v = "%.5f" % v
	
	def string_parse(self, v):
		return float(v)


