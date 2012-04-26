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

import sys, struct, time
import math, heapq
import curses

VIS_GRADIENT = " .,:;!i$@#"
ATMOS_MIN_DELTA = 0.01
ATMOS_MIN_PRESSURE = 0.01
ATMOS_MIN_MIX_PRESSURE = 0.0001
ATMOS_MIN_FLOW = 0.00002
ATMOS_UPDATES_PER_TICK = 500
ATMOS_UPDATES_FRAME_FACTOR = 0.01
ATMOS_FLOW_ADJUST = 0.95

def get_gradient(v, l, h):
	iv = v
	v = max(l, min(h, v))
	v = (v-l)/(h-l)
	v = (v*(len(VIS_GRADIENT)-1)+0.5)
	fv = v
	v = int(v)
	assert v >= 0 and v < len(VIS_GRADIENT), "%i %s %s %s %s" % (v, iv, fv, l, h)
	return VIS_GRADIENT[v]

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

class Entity:
	type_name = "EDOOFUS:defineme!"
	ch = "?"
	col = 0x07
	# yeah, this isn't done yet --GM

class PlayerEntity(Entity):
	type_name = "Player"
	ch = "@"
	col = 0x07

class Tile:
	type_name = "EDOOFUS:defineme!"
	ch = "?"
	col = 0x07
	solid = False
	broken = False
	pres_lvl_air = 1.0
	pres_lvl_plasma = 0.0
	pres_lvl_toxins = 0.0
	pres_flow = 1.0
	pres_tol_min = 4.5 # leaking point (linear pres_flow->pres_tol_leakmax)
	pres_tol_max = 5.0 # breaking point
	pres_tol_leakmax = 0.07 # how much can leak before the thing breaks
	pres_tol_ch = ";"
	heat_lvl = 293.15 # 293.15 Kelvin == 20 Celcius
	heat_flow = 0.9
	
	def __init__(self, world, x, y):
		self.world = world
		self.x, self.y = x,y
	
	def save(self, fp):
		# store ch, col
		# we must ensure at least one byte is written wrt ch
		fp.write(chr(ord(self.ch))+chr(self.col))
		
		# store flags
		fp.write(chr(0
			| (1 if self.solid else 0) # bit 0 = solid
			| (2 if self.broken else 0) # bit 1 = broken
		))
		
		# store atmos crap
		# note, floats must be used because pressure can get very, very high
		fp.write(struct.pack("<ffffff"
			,self.get_pres_air(), self.get_pres_plasma(), self.get_pres_toxins(), self.get_pres_flow()
			,self.get_heat(), self.get_heat_flow()))
		
		# store anything else this tile needs
		self.save_extra(fp)
	
	def load(self, fp):
		# load ch, col
		self.ch = fp.read(1)
		self.col = ord(fp.read(1))
		
		# load flags
		flags = ord(fp.read(1))
		self.solid = not not (flags & 1) # bit 0 = solid
		self.broken = not not (flags & 2) # bit 1 = broken
		
		# load atmos crap
		(
			self.pres_lvl_air, self.pres_lvl_plasma, self.pres_lvl_toxins, self.pres_flow,
			self.heat_lvl, self.heat_flow
		) = struct.unpack("<ffffff",fp.read(4*6))
		
		# load anything else this tile needs
		self.load_extra(fp)
	
	def save_extra(self, fp):
		pass
	
	def load_extra(self, fp):
		pass
	
	def become_broken(self):
		self.solid = False
		self.broken = True
		self.pres_flow = 1.0
		self.set_ch_col(ch=self.pres_tol_ch)
	
	def stress(self, pt):
		f = self.pres_flow
		ptf = pt*(1.0-f)
		if ptf > self.pres_tol_min:
			f = (
				(ptf-self.pres_tol_min)
				*(self.pres_tol_leakmax-self.pres_flow)
				/(self.pres_tol_max-self.pres_tol_min)
				+self.pres_flow
			)
		if ptf > self.pres_tol_max:
			self.become_broken()
			f = self.pres_flow
		
		return f
	
	def add_pres(self, air=0.0, plasma=0.0, toxins=0.0, heat=0.0):
		self.pres_lvl_air += air
		self.pres_lvl_plasma += plasma
		self.pres_lvl_toxins += toxins
		self.heat_lvl += heat
		
		self.world.enqueue_atmos_update(self.x, self.y)
	
	def set_ch_col(self, ch=None, col=None):
		if ch != None:
			self.ch = ch
		if col != None:
			self.col = col
		
		self.world.defer_draw_tile(self.x, self.y)
	
	def update_atmos_pres(self, tn, ts, tw, te):
		# TODO: improve this algorithm
		# there's a lot of "stuff i might need" in here
		# which isn't actually used --GM
		
		# get pressures
		pc = self.get_pres()
		pn, ps, pw, pe = (t.get_pres() for t in (tn,ts,tw,te))
		
		# get flows
		#fc = self.get_pres_flow()
		fc = self.stress(pc)
		if fc == 0.0:
			return # don't change pressure if it can't flow at all
		fn, fs, fw, fe = (t.stress(p) for t,p in zip((tn,ts,tw,te),(pn,ps,pw,pe)) )
		
		# calculate total flow
		ftotal = fn+fs+fw+fe
		if ftotal < ATMOS_MIN_FLOW:
			return # don't change pressure if it can't flow adequately
		
		# calculate various pressure values
		pctotal = pn*fn+ps*fs+pw*fw+pe*fe
		ptotal = pc+pctotal
		xftotal = ftotal+1.0
		pmean = pctotal/xftotal
		
		# NOTE:
		# if fn,fs,fw,fe all == 1.0, then end result must be that pc==pn==ps==pw==pe.
		# npc = opc - (npn-opn) - (nps-ops) - (npw-opw) - (npe-ope) = (opc+opn+ops+opw+ope)/5
		# this ONLY applies when all flows == 1.0!	
		
		# get pressure contents
		pl_air = self.get_pres_air()
		pl_plasma = self.get_pres_plasma()
		pl_toxins = self.get_pres_toxins()
		pl_heat = self.get_heat() # TODO: split this into pressure and heat?
		
		for t,p,f in zip((tn,ts,tw,te),(pn,ps,pw,pe),(fn,fs,fw,fe)):
			# calculate pressure to transfer
			#c = (pmean-p)*fc*ATMOS_FLOW_ADJUST/xftotal
			c = (pmean-p)*fc*ATMOS_FLOW_ADJUST/5.0
			
			# calculate total for gas proportions
			xd = p+pc
			if xd < ATMOS_MIN_MIX_PRESSURE:
				# the pressure is too low to work out the gas proportions
				# don't transfer a damn thing
				self.world.enqueue_atmos_update(t.x, t.y)
				t.collapse_pres()
				continue
			
			# calculate gas proportions
			xpl_air = (pl_air + t.get_pres_air())/xd
			xpl_plasma = (pl_plasma + t.get_pres_plasma())/xd
			xpl_toxins = (pl_toxins + t.get_pres_toxins())/xd
			xpl_heat = (pl_heat + t.get_heat())/xd
			
			# transfer pressure
			flow = t.stress(xd*c)
			t.add_pres(air=xpl_air*c*flow, plasma=xpl_plasma*c*flow, toxins=xpl_toxins*c*flow, heat=xpl_heat*c*flow)
			c = -c
			self.add_pres(air=xpl_air*c*flow, plasma=xpl_plasma*c*flow, toxins=xpl_toxins*c*flow, heat=xpl_heat*c*flow)
			t.collapse_pres()
		
		self.collapse_pres()
		
		self.world.enqueue_atmos_update(self.x, self.y)
	
	def collapse_pres(self):
		if self.get_pres_air() < ATMOS_MIN_PRESSURE:
			self.pres_lvl_air = 0.0
		if self.get_pres_plasma() < ATMOS_MIN_PRESSURE:
			self.pres_lvl_plasma = 0.0
		if self.get_pres_toxins() < ATMOS_MIN_PRESSURE:
			self.pres_lvl_toxins = 0.0
		if self.get_heat() < ATMOS_MIN_PRESSURE:
			self.heat_lvl = 0.0
	
	def get_atmos_delta(self, tn, ts, tw, te):
		# get flows
		fc = self.get_pres_flow()
		if fc == 0.0:
			return 0.0 # don't change pressure if it can't flow at all
		fn, fs, fw, fe = (t.get_pres_flow() for t in (tn,ts,tw,te))
		
		# get pressures
		pc = self.get_pres()
		pn, ps, pw, pe = (t.get_pres() for t in (tn,ts,tw,te))
		
		# return delta
		#return abs((pn-pc)*fn + (ps-pc)*fs + (pw-pc)*fw + (pe-pc)*fe)*fc
		return (abs(pn-pc)*fn + abs(ps-pc)*fs + abs(pw-pc)*fw + abs(pe-pc)*fe)*fc
	
	def get_pres(self):
		return self.get_pres_air() + self.get_pres_plasma() + self.get_pres_toxins()
	
	def get_pres_air(self):
		return self.pres_lvl_air
	
	def get_pres_plasma(self):
		return self.pres_lvl_plasma
	
	def get_pres_toxins(self):
		return self.pres_lvl_toxins
	
	def get_pres_flow(self):
		v = self.pres_flow
		
		if v <= 0.000001:
			return 0
		
		return v
	
	def get_heat(self):
		return self.heat_lvl
	
	def get_heat_flow(self):
		v = self.heat_flow
		
		if v <= 0.000001:
			return 0
		
		return v
	
	def get_ch(self):
		return self.ch
	
	def get_editables(self):
		return {
			"pres_lvl_air" : FloatEditable,
			"pres_lvl_plasma" : FloatEditable,
			"pres_lvl_toxins" : FloatEditable,
			"pres_flow" : FloatEditable,
			"heat_lvl" : FloatEditable,
			#"heat_flow" : FloatEditable, # TODO?
		}
	
	def on_touch(self, entity=None, item=None):
		pass

class SpaceTile(Tile):
	type_name = "Space"
	ch = " "
	solid = False
	pres_lvl_air = 0.0
	heat_lvl = 0.0

class BorderTile(SpaceTile):
	type_name = "Border"
	solid = True
	
	def add_pres(self, air=0.0, plasma=0.0, toxins=0.0, heat=0.0):
		return
	
	def get_pres_air(self):
		return 0.0
	
	def get_pres_plasma(self):
		return 0.0
	
	def get_pres_toxins(self):
		return 0.0
	
	def get_heat(self):
		return 0.0
	
	def get_editables(self):
		return {}

class FloorTile(Tile):
	type_name = "Floor"
	ch = "."
	solid = False

class WallTile(Tile):
	type_name = "Wall"
	ch = "#"
	col = 0x07
	solid = True
	pres_flow = 0.0
	heat_flow = 0.0

class DoorTile(Tile):
	type_name = "Door"
	ch = "-"
	col = 0x07
	solid = True
	pres_flow = 0.0
	heat_flow = 0.0
	
	door_is_open = False
	
	def save_extra(self, fp):
		# flags
		fp.write(chr(0
			| (1 if self.door_is_open else 0) # bit 0 = door_is_open
		))
	
	def load_extra(self, fp):
		# flags
		flags = ord(fp.read(1))
		self.door_is_open = not not (flags & 1) # bit 0 = door_is_open
	
	def on_touch(self, entity=None, item=None):
		# TODO: permissions
		self.door_is_open = not self.door_is_open
		
		if self.door_is_open:
			self.set_ch_col(ch="=")
			self.pres_flow = 1.0
			self.heat_flow = 1.0
		else:
			self.set_ch_col(ch="-")
			self.pres_flow = 0.0
			self.heat_flow = 0.0
		
		self.world.enqueue_atmos_update(self.x, self.y)

class ValveTile(Tile):
	type_name = "Valve"
	ch = "^"
	col = 0x07
	solid = True
	pres_flow = 0.0
	pres_lvl_air = 0.0

class TankTile(Tile):
	type_name = "Tank"
	ch = "$"
	col = 0x07
	solid = True
	pres_flow = 0.0
	pres_lvl_air = 0.0

TILE_TYPES = [
	SpaceTile,FloorTile,WallTile,
	DoorTile,ValveTile,TankTile,
]

TILE_EXAMPLES = [t(None,-1,-1) for t in TILE_TYPES]

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
			tc = BorderTile if tt == -1 else TILE_TYPES[tt]
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
			  [[BorderTile(self,x,0) for x in xrange(w)]]
			+ [[BorderTile(self,0,y+1)]+[SpaceTile(self,x+1,y+1) for x in xrange(w-2)]+[BorderTile(self,w-1,y+1)]
				for y in xrange(h-2)]
			+ [[BorderTile(self,x,h-1) for x in xrange(w)]]
		)
	
	def save_world(self, fname):
		fp = open(fname, "wb")
		fp.write("SS3-14\x1A\x01")
		fp.write(struct.pack("<HH", self.w, self.h))
		
		for y in xrange(self.h):
			for x in xrange(self.w):
				t = self.g[y][x]
				tc = t.__class__
				tt = -1 if tc == BorderTile else TILE_TYPES.index(tc)
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
		
		ws.addstr(y,x,get_gradient(t.get_pres(), 0.0, 1.0))
	
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
		pc = tc.get_pres()
		pn = (pc-tn.get_pres())*tn.get_flow()
		ps = (pc-ts.get_pres())*ts.get_flow()
		pw = (pc-tw.get_pres())*tw.get_flow()
		pe = (pc-te.get_pres())*te.get_flow()
		
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

class Game:
	def __init__(self, fname):
		self.world = GameWorld.load_world(fname)

class WorldEditor:
	def __init__(self, gs, fname, w=128, h=128):
		self.fname = fname
		self.world = None
		try:
			self.world = load_new_world(fname)
		except IOError:
			self.world = GameWorld(w, h) # file didn't exist
		
		self.gs = gs
		gsh, gsw = self.gs.getmaxyx()
		self.ws = curses.newpad(h+1, w+1) # to get around a bug where (w-1,h-1) is inaccessible
		self.ws.clear()
		self.curx, self.cury = w//2, h//2
		self.camx, self.camy = (w-gsw)//2, (h-gsh)//2
		self.picked_tile = 0
		self.autodraw = False
		self.running = False
		self.repaint()
	
	def repaint(self):
		self.world.repaint_on(self.ws)
	
	def update_screen(self):
		gsh, gsw = self.gs.getmaxyx()
		w, h = self.world.get_size()
		
		if self.curx < self.camx:
			self.camx = self.curx
		if self.cury < self.camy:
			self.camy = self.cury
		if self.curx >= self.camx+gsw:
			self.camx = self.curx-(gsw-1)
		if self.cury >= self.camy+(gsh-1):
			self.camy = self.cury-((gsh-1)-1)
		
		self.world.flush_draw_queue(self.ws)
		self.ws.overwrite(self.gs, self.camy, self.camx, 0, 0, min(h, gsh-2), min(w, gsw-1))
		self.gs.addstr(gsh-1,0,"[%i,%i]" % (self.curx, self.cury))
		self.gs.clrtoeol()
		self.gs.addstr(gsh-1,10,"WldT: [ ] %s" % (self.world.g[self.cury][self.curx].type_name))
		self.gs.addstr(gsh-1,17,self.world.g[self.cury][self.curx].get_ch())
		self.gs.addstr(gsh-1,35,"%s: %3i [ ] %s" % ("DRAW" if self.autodraw else "PicT"
			, self.picked_tile, TILE_EXAMPLES[self.picked_tile].type_name))
		self.gs.addstr(gsh-1,42+4,TILE_EXAMPLES[self.picked_tile].get_ch())
		self.gs.addstr(gsh-1,70,"ATM: %i" % len(self.world.atmos_queue))
		#q = self.world.g[self.cury][self.curx].get_atmos_delta(
		#	self.world.g[self.cury-1][self.curx],
		#	self.world.g[self.cury+1][self.curx],
		#	self.world.g[self.cury][self.curx-1],
		#	self.world.g[self.cury][self.curx+1],
		#)
		#self.gs.addstr(gsh-1,60,"%.5f" % (q or 0.0))
		self.gs.addstr(gsh-1,60,"%.5f" % self.world.g[self.cury][self.curx].get_pres())
		self.gs.addstr(self.cury - self.camy, self.curx - self.camx, "")
		self.gs.refresh()
	
	def put_tile(self, x, y, tile):
		self.world.g[y][x] = tile
		self.world.draw_tile(self.ws, x, y)
		self.world.enqueue_atmos_update(x,y)
	
	def put_tile_cur(self):
		self.put_tile(self.curx, self.cury, TILE_TYPES[self.picked_tile](self.world, self.curx, self.cury))
	
	def check_autodraw(self):
		if self.autodraw:
			self.put_tile_cur()
	
	def run(self):
		while True:
			gsh, gsw = self.gs.getmaxyx()
			w, h = self.world.get_size()
			
			k = self.gs.getch()
			k = "" if k == -1 else chr(k)
			
			if k == "\x1B":
				k = self.gs.getkey()
				if k == "[":
					k = self.gs.getkey()
					if k == "A":
						self.cury = max(1, self.cury-1)
						self.check_autodraw()
					elif k == "B":
						self.cury = min(h-2, self.cury+1)
						self.check_autodraw()
					elif k == "C":
						self.curx = min(w-2, self.curx+1)
						self.check_autodraw()
					elif k == "D":
						self.curx = max(1, self.curx-1)
						self.check_autodraw()
			elif k == "[":
				self.picked_tile = max(0, self.picked_tile-1)
			elif k == "]":
				self.picked_tile = min(len(TILE_TYPES)-1, self.picked_tile+1)
			elif k == " ":
				self.put_tile_cur()
			elif k == "\n":
				npt = TILE_TYPES.index(self.world.g[self.cury][self.curx].__class__)
				if npt != -1:
					self.picked_tile = npt
			elif k == "\t":
				self.autodraw = not self.autodraw
				if self.autodraw:
					self.put_tile_cur()
			elif k == "T":
				self.world.tick_full(self.ws)
			elif k == "r":
				self.running = not self.running
			elif k == "t":
				self.world.tick(self.ws)
			elif k == "p":
				self.world.pressure_view = not self.world.pressure_view
				self.repaint()
			elif k == "P":
				self.world.g[self.cury][self.curx].add_pres(air=1.0)
			elif k == "e":
				self.world.g[self.cury][self.curx].on_touch()
			elif k == "S":
				self.world.save_world(self.fname)
			
			if self.running:
				self.world.tick(self.ws)
			
			self.update_screen()
			time.sleep(0.02)

working_fname = sys.argv[1]

try:
	gs = curses.initscr()
	gs.clear()
	gs.nodelay(1)
	curses.noecho()
	we = WorldEditor(gs,working_fname,128,128)
	we.run()
finally:
	curses.endwin()

