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

import curses, time

from const import *
import common
import world, tile

class WorldEditor:
	def __init__(self, gs, fname, w=128, h=128):
		self.fname = fname
		self.world = None
		try:
			self.world = world.load_new_world(fname)
		except IOError:
			self.world = world.GameWorld(w, h) # file didn't exist
		
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
			, self.picked_tile, tile.TILE_EXAMPLES[self.picked_tile].type_name))
		self.gs.addstr(gsh-1,42+4,tile.TILE_EXAMPLES[self.picked_tile].get_ch())
		self.gs.addstr(gsh-1,70,"ATM: %i" % len(self.world.atmos_queue))
		#q = self.world.g[self.cury][self.curx].get_atmos_delta(
		#	self.world.g[self.cury-1][self.curx],
		#	self.world.g[self.cury+1][self.curx],
		#	self.world.g[self.cury][self.curx-1],
		#	self.world.g[self.cury][self.curx+1],
		#)
		#self.gs.addstr(gsh-1,60,"%.5f" % (q or 0.0))
		self.gs.addstr(gsh-1,60,"%.5f" % self.world.g[self.cury][self.curx].get_pres((0,0)))
		self.gs.addstr(self.cury - self.camy, self.curx - self.camx, "")
		self.gs.refresh()
	
	def put_tile(self, x, y, tile):
		self.world.g[y][x] = tile
		self.world.draw_tile(self.ws, x, y)
		self.world.enqueue_atmos_update(x,y)
	
	def put_tile_cur(self):
		self.put_tile(self.curx, self.cury, tile.TILE_TYPES[self.picked_tile](self.world, self.curx, self.cury))
	
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
				self.picked_tile = min(len(tile.TILE_TYPES)-1, self.picked_tile+1)
			elif k == " ":
				self.put_tile_cur()
			elif k == "\n":
				npt = tile.TILE_TYPES.index(self.world.g[self.cury][self.curx].__class__)
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

