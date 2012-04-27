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

import struct, heapq

from const import *
import common
import tile, entity

def load_new_world(fname):
	fp = open(fname, "rb")
	
	magic = fp.read(8)
	if magic != "SS3-14\x1A\x01":
		raise WorldFormatException("not an SS3-14 v1 world")
	
	w, h = struct.unpack("<HH", fp.read(4))
	world = GameWorld(w, h)
	
	for y in xrange(h):
		for x in xrange(w):
			tt, = struct.unpack("<h",fp.read(2))
			tc = tile.BorderTile if tt == -1 else tile.TILE_TYPES[tt]
			t = tc(world, x, y)
			t.load(fp)
			world.g[y][x] = t
	
	fp.close()
	
	return world

class GameWorld:
	class WorldFormatException(Exception):
		pass
	
	ftime = 0
	
	def __init__(self, w, h):
		self.w, self.h = w, h
		
		self.pressure_view = False
		
		self.atmos_queue = []
		self.atmos_set = set()
		
		self.draw_queue = []
		self.draw_set = set()
		self.g = (
			  [[tile.BorderTile(self,x,0) for x in xrange(w)]]
			+ [[tile.BorderTile(self,0,y+1)]+[tile.SpaceTile(self,x+1,y+1) for x in xrange(w-2)]+[tile.BorderTile(self,w-1,y+1)]
				for y in xrange(h-2)]
			+ [[tile.BorderTile(self,x,h-1) for x in xrange(w)]]
		)
	
	def save_world(self, fname):
		fp = open(fname, "wb")
		fp.write("SS3-14\x1A\x01")
		fp.write(struct.pack("<HH", self.w, self.h))
		
		for y in xrange(self.h):
			for x in xrange(self.w):
				t = self.g[y][x]
				tc = t.__class__
				tt = -1 if tc == tile.BorderTile else tile.TILE_TYPES.index(tc)
				fp.write(struct.pack("<h", tt))
				t.save(fp)
		
		fp.close()
	
	def defer_draw_tile(self, x, y):
		if (x,y) not in self.draw_set:
			self.draw_queue.append((x,y))
			self.draw_set.add((x,y))
	
	def repaint_pres_on(self, ws):
		for y in xrange(self.h):
			for x in xrange(self.w):
				t = self.g[y][x]
				self.draw_tile_pres(ws, x, y)
	
	def draw_tile_pres(self, ws, x, y):
		t = self.g[y][x]
		gsh, gsw = ws.getmaxyx()
		
		assert x >= 0
		assert y >= 0
		assert x < self.w
		assert y < self.h
		assert x < gsw
		assert y < gsh
		
		ws.addstr(y,x,common.get_twogradient(t.get_pres((0,0)), 0.0, t.pres_tol_min, t.pres_tol_max))
	
	def repaint_on(self, ws):
		if self.pressure_view:
			return self.repaint_pres_on(ws)
		
		for y in xrange(self.h):
			for x in xrange(self.w):
				self.draw_tile(ws, x, y)
	
	def draw_tile(self, ws, x, y):
		if self.pressure_view:
			return self.draw_tile_pres(ws, x, y)
		
		t = self.g[y][x]
		gsh, gsw = ws.getmaxyx()
		
		assert len(t.get_ch()) == 1
		assert x >= 0
		assert y >= 0
		assert x < self.w
		assert y < self.h
		assert x < gsw
		assert y < gsh
		
		try:
			ws.addstr(y,x,t.get_ch())
		except Exception:
			assert False, "%i %i %s [%i,%i]" % (y,x,t.get_ch(),gsw,gsh)
	
	def get_atmos_vec(self, x, y):
		if x <= 0 or x >= self.w-1 or y <= 0 or y >= self.h-1:
			return (0,0)
		
		tc = self.g[y][x]
		tn = self.g[y-1][x]
		ts = self.g[y+1][x]
		tw = self.g[y][x-1]
		te = self.g[y][x+1]
		
		fc = tc.get_pres_flow()
		pc = tc.get_pres((0,0))
		pn = (pc-tn.get_pres((0,-1)))*tn.get_flow()
		ps = (pc-ts.get_pres((0,1)))*ts.get_flow()
		pw = (pc-tw.get_pres((-1,0)))*tw.get_flow()
		pe = (pc-te.get_pres((1,0)))*te.get_flow()
		
		return ((ps-pn), te-tw)
	
	def get_size(self):
		return self.w, self.h
	
	def enqueue_atmos_update(self, x, y):
		# don't enqueue new atmos updates!
		if (x,y) in self.atmos_set:
			return
		
		t = self.g[y][x]
		tn, ts, tw, te = (self.g[y+v][x+u] for u,v in ((0,-1),(0,1),(-1,0),(1,0)))
		tp = t.get_atmos_delta(tn, ts, tw, te)
		
		if tp > ATMOS_MIN_DELTA:
			heapq.heappush(self.atmos_queue, (-(tp-self.ftime*ATMOS_UPDATES_FRAME_FACTOR), (x,y)))
			self.atmos_set.add((x,y))
	
	def flush_draw_queue(self, ws):
		for (x,y) in self.draw_queue:
			self.draw_tile(ws, x, y)
		
		self.draw_queue = []
		self.draw_set = set()
	
	def tick(self, ws):
		self.ftime += 1
		l = [heapq.heappop(self.atmos_queue)
			for i in xrange(min(len(self.atmos_queue),ATMOS_UPDATES_PER_TICK))]
		
		for _,(x,y) in l:
			self.atmos_set.remove((x,y))
		
		for _,(x,y) in l:
			t = self.g[y][x]
			tn, ts, tw, te = (self.g[y+v][x+u] for u,v in ((0,-1),(0,1),(-1,0),(1,0)))
			t.update_atmos_pres(tn, ts, tw, te)
			self.enqueue_atmos_update(x, y)
			if self.pressure_view:
				self.defer_draw_tile(x,y)
		
		self.flush_draw_queue(ws)
	
	def tick_full(self, ws):
		# clear queues + sets
		self.atmos_queue = []
		self.atmos_set = set()
		self.draw_queue = []
		self.draw_set = set()
		
		# enqueue all atmos tiles where necessary
		for y in xrange(1, self.h-1, 1):
			for x in xrange(1, self.w-1, 1):
				self.enqueue_atmos_update(x, y)
				self.defer_draw_tile(x, y)
		
		# now do regular tick
		self.tick(ws)

