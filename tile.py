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

import struct

from const import *
import common

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
	pres_tol_min = 4.0 # leaking point (linear pres_flow->pres_tol_leakmax)
	pres_tol_max = 5.0 # breaking point
	pres_tol_leakmax = 0.2 # how much can leak before the thing breaks
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
	
	def stress(self, pt, (u,v)):
		if self.broken:
			return 1.0
		
		f = self.get_pres_flow((u,v))
		ptf = pt*(1.0-f)
		#xmin = 1.0 if toself else self.pres_tol_min
		xmin = self.pres_tol_min
		if ptf > xmin:
			f = (
				(ptf-xmin)
				*(self.pres_tol_leakmax-f)
				/(self.pres_tol_max-xmin)
				+f
			)
		#ptf = pt*(1.0-f)
		if ptf > self.pres_tol_max:
			self.become_broken()
			return 1.0
		
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
		pc = self.get_pres((0,0))
		pn, ps, pw, pe = (t.get_pres((u,v)) for t,(u,v) in zip((tn,ts,tw,te),DIR_LIST_NSWE) )
		
		# get flows
		#fc = self.get_pres_flow()
		fc = self.stress(pc, (0,0))
		if fc == 0.0:
			return # don't change pressure if it can't flow at all
		fn, fs, fw, fe = (t.stress(p, (u,v)) for t,p,(u,v) in 
			zip((tn,ts,tw,te),(pn,ps,pw,pe),DIR_LIST_NSWE) )
		
		# calculate total flow
		ftotal = fn+fs+fw+fe
		if ftotal < ATMOS_MIN_FLOW:
			return # don't change pressure if it can't flow adequately
		
		# calculate various pressure values
		pctotal = pn*fn+ps*fs+pw*fw+pe*fe
		ptotal = pc+pctotal
		xftotal = ftotal+1.0
		pmean = ptotal/xftotal
		
		# NOTE:
		# if fn,fs,fw,fe all == 1.0, then end result must be that pc==pn==ps==pw==pe.
		# npc = opc - (npn-opn) - (nps-ops) - (npw-opw) - (npe-ope) = (opc+opn+ops+opw+ope)/5
		# this ONLY applies when all flows == 1.0!	
		
		# get pressure contents
		pl_air = self.get_pres_air()
		pl_plasma = self.get_pres_plasma()
		pl_toxins = self.get_pres_toxins()
		pl_heat = self.get_heat() # TODO: split this into pressure and heat?
		
		for t,p,f,(u,v) in zip((tn,ts,tw,te),(pn,ps,pw,pe),(fn,fs,fw,fe),DIR_LIST_NSWE):
			# calculate pressure to transfer
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
			flow = t.stress(xd*c, (u,v))
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
		# get pressures
		pc = self.get_pres((0,0))
		pn, ps, pw, pe = (t.get_pres((u,v)) for t,(u,v) in zip((tn,ts,tw,te),DIR_LIST_NSWE) )
		
		# get flows
		fc = self.stress(pc, (0,0))
		if fc == 0.0:
			return 0.0 # don't change pressure if it can't flow at all
		fn, fs, fw, fe = (t.stress(pc*ATMOS_FLOW_ADJUST/5.0, (u,v)) for t,p,(u,v)
			in zip((tn,ts,tw,te),(pn,ps,pw,pe),DIR_LIST_NSWE) )
		
		# return delta
		#return abs((pn-pc)*fn + (ps-pc)*fs + (pw-pc)*fw + (pe-pc)*fe)*fc
		return (abs(pn-pc)*fn + abs(ps-pc)*fs + abs(pw-pc)*fw + abs(pe-pc)*fe)*fc
	
	def get_pres(self, (u,v)=(None,None)):
		return self.get_pres_air() + self.get_pres_plasma() + self.get_pres_toxins()
	
	def get_pres_air(self):
		return self.pres_lvl_air
	
	def get_pres_plasma(self):
		return self.pres_lvl_plasma
	
	def get_pres_toxins(self):
		return self.pres_lvl_toxins
	
	def get_pres_flow(self, (u,v)=(None,None)):
		r = self.pres_flow
		
		if r <= 0.000001:
			return 0
		
		return r
	
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
	pres_tol_min = 4.0
	pres_tol_max = 15.0
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
	pres_tol_min = 4.0
	pres_tol_max = 15.0

class WallTile(Tile):
	type_name = "Wall"
	ch = "#"
	col = 0x07
	solid = True
	pres_lvl_air = 4.0
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
		if self.broken:
			return
		
		self.door_is_open = not self.door_is_open
		
		self.solid = not self.door_is_open
		
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
	ch = "|"
	col = 0x07
	solid = True
	pres_flow = 0.0
	pres_lvl_air = 0.5
	pres_tol_min = 0.5
	pres_tol_max = 6.0
	pres_tol_leakmax = 0.7
	
	valve_is_open = False
	
	def save_extra(self, fp):
		# flags
		fp.write(chr(0
			| (1 if self.valve_is_open else 0) # bit 0 = valve_is_open
		))
	
	def load_extra(self, fp):
		# flags
		flags = ord(fp.read(1))
		self.valve_is_open = not not (flags & 1) # bit 0 = valve_is_open
	
	def on_touch(self, entity=None, item=None):
		# TODO: permissions
		if self.broken:
			return
		
		self.valve_is_open = not self.valve_is_open
		
		if self.valve_is_open:
			self.set_ch_col(ch="^")
			self.pres_flow = 1.0
			self.heat_flow = 1.0
		else:
			self.set_ch_col(ch="|")
			self.pres_flow = 0.0
			self.heat_flow = 0.0
		
		self.world.enqueue_atmos_update(self.x, self.y)

class TankTile(Tile):
	type_name = "Tank"
	ch = "$"
	col = 0x07
	solid = True
	pres_flow = 0.0
	pres_lvl_air = 250.0
	pres_tol_min = 300.0
	pres_tol_max = 350.0
	pres_tol_leakmax = 0.01

class PumpTile(Tile):
	type_name = "Pump"
	ch = "^"
	col = 0x07
	solid = False
	pres_flow = 0.03
	pres_lvl_air = 1.0
	pres_tol_min = 100.0
	pres_tol_max = 150.0
	pres_tol_leakmax = 0.04
	
	pump_dir = 0 # North
	
	def save_extra(self, fp):
		# pump direction
		fp.write(chr(self.pump_dir))
	
	def load_extra(self, fp):
		# pump direction
		self.pump_dir = ord(fp.read(1))
	
	def on_touch(self, entity=None, item=None):
		if self.broken:
			return
		
		self.pump_dir = (self.pump_dir+1)&3
		self.set_ch_col(ch="^v<>"[self.pump_dir])
		
		self.world.enqueue_atmos_update(self.x, self.y)
	
	def pump_get_params(self):
		zu,zv = DIR_LIST_NSWE[self.pump_dir]
		to = self.world.g[self.y+zv][self.x+zu]
		ti = self.world.g[self.y-zv][self.x-zu]
		po = to.get_pres((-zu,-zv))
		pi = to.get_pres((zu,zv))
		fo = to.get_pres_flow((-zu,-zv))
		fi = to.get_pres_flow((zu,zv))
		
		return zu,zv,to,ti,po,pi,fo,fi
	
	def get_pres(self, (u,v)=(None,None)):
		zu,zv,to,ti,po,pi,fo,fi = self.pump_get_params()
		
		rp = Tile.get_pres(self,(u,v))
		
		if u == -zu and v == -zv:
			return rp+min(max(rp,0.0),2.0)
		elif u == zu and v == zv:
			return max(0,rp-2.0)
		else:
			return rp
	
	def get_pres_flow(self, (u,v)=(None,None)):
		zu,zv,to,ti,po,pi,fo,fi = self.pump_get_params()
		
		if u == None or (zu == 0) == (u == 0) or ((u == 0) and (v == 0)):
			return self.pres_flow
		else:
			return 0.0

TILE_TYPES = [
	SpaceTile,FloorTile,WallTile,
	DoorTile,ValveTile,TankTile,
	PumpTile,
]

TILE_EXAMPLES = [t(None,-1,-1) for t in TILE_TYPES]

