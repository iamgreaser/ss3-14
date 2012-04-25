import sys
import time

COLMAP = [0,4,2,6,1,5,3,7]

def flip_fix_xy(f):
	def _f1(self, x1, y1, x2, y2, *args, **kwargs):
		if x1 > x2:
			x1, x2 = x2, x1
		if y1 > y2:
			y1, y2 = y2, y1
		
		if x2 < 0 or x1 >= self.w:
			return None
		if y2 < 0 or y1 >= self.h:
			return None
		
		odx, ody = self.get_pos()
		
		ret = f(self, x1, y1, x2, y2, *args, **kwargs)
		
		self.set_pos(odx, ody)
		
		return ret
	
	return _f1

class GameScreen:
	def __init__(self, w=80, h=23):
		self.resize(w,h)
		self.set_cursor(0,0)
		self.ccol = 0x07
	
	def resize(self, w, h):
		self.w, self.h = w, h
		self.g = [[[' ',0x07] for x in xrange(self.w)] for y in xrange(self.h)]
	
	def set_cursor(self, x, y):
		self.cx = max(0,min(self.w-1,x))
		self.cy = max(0,min(self.h-1,y))
	
	def __set_pos(self, x, y):
		x = max(0,min(self.w-1,x))
		y = max(0,min(self.h-1,y))
		sys.stdout.write("\x1B[%i;%iH" % (y+1,x+1))
	
	def set_pos(self, x, y):
		self.dx = max(0,min(self.w-1,x))
		self.dy = max(0,min(self.h-1,y))
		self.__set_pos(self.dx, self.dy)
	
	def get_pos(self):
		return self.dx, self.dy
	
	def __set_color(self, col):
		fg = col & 0x7
		bg = (col >> 4) & 0x7
		blink = col & 0x80
		bold = col & 0x08
		
		s = "\x1B[0"
		if blink:
			s += ";5"
		if bold:
			s += ";1"
		if fg != 7:
			s += ";3%i" % COLMAP[fg]
		if bg != 0:
			s += ";4%i" % COLMAP[bg]
		
		sys.stdout.write(s+"m")
	
	def set_color(self, col):
		self.__set_color(col)
		self.ccol = col
	
	def __write(self, s):
		sys.stdout.write(s)
		for c in s:
			self.g[self.dy][self.dx] = [c,self.ccol]
			self.dx += 1
	
	def write(self, s):
		while self.dx+len(s) >= self.w:
			d = w-self.dx+len(s)
			cs, s = s[:d], s[d:]
			self.__write(cs)
			self.set_pos(0, self.dy+1)
		
		self.__write(s)
	
	@flip_fix_xy
	def fill_rect(self, x1, y1, x2, y2, ch):
		x1, x2 = (max(0,min(self.w-1,x)) for x in (x1,x2))
		y1, y2 = (max(0,min(self.h-1,y)) for y in (y1,y2))
		
		for y in xrange(y1,y2+1,1):
			self.set_pos(x1,y)
			self.write(ch*(x2-x1+1))
	
	@flip_fix_xy
	def draw_rect(self, x1, y1, x2, y2, ch):
		x1, x2 = (max(0,min(self.w-1,x)) for x in (x1,x2))
		
		for y in (y1,y2):
			if y >= 0 and y < self.h:
				self.set_pos(x1,y)
				self.write(ch*(x2-x1+1))
		
		y1, y2 = (max(0,min(self.h-1,y)) for y in (y1,y2))
		
		for x in (x1,x2):
			for y in xrange(y1,y2+1,1):
				self.set_pos(x,y)
				self.write(ch)
	
	def scroll(self, x, y):
		odx, ody = self.get_pos()
		ocx, ocy = self.get_cursor()
		
		clearme = abs(y) >= self.h or abs(x) >= self.w
		
		if clearme:
			self.resize(self.w, self.h)
		else:
			if y > 0:
				self.g = self.g[y:] + [[[' ',0x07] for j in xrange(self.w)] for i in xrange(y)]
			elif y < 0:
				self.g = [[[' ',0x07] for j in xrange(self.w)] for i in xrange(-y)] + self.g[:self.h+y]
			
			if x != 0:
				for l in self.g:
					if x > 0:
						l = l[x:] + [[' ',0x07] for j in xrange(x)]
					elif x < 0:
						l = [[' ',0x07] for j in xrange(-x)] + l[:self.w+x]
		
		self.set_cursor(ocx-x, ocy-y)
		self.set_pos(odx-x, ody-y)
		self.repaint()
	
	def __clear_screen(self):
		sys.stdout.write("\x1B[0m\x1B[2J")
	
	def clear_screen(self):
		self.__clear_screen()
		self.resize(self.w, self.h)
	
	def flush(self):
		self.__set_pos(self.cx, self.cy)
		sys.stdout.flush()
	
	def repaint(self):
		cdef = -1
		self.__clear_screen()
		self.__set_pos(0,0)
		for y,l in zip(xrange(self.h),self.g):
			self.__set_pos(0,y)
			for ch, col in l:
				if col != cdef:
					self.__set_color(col)
					cdef = col
				
				sys.stdout.write(ch)
		
		self.flush()

gs = GameScreen(79,23)
gs.clear_screen()
gs.set_pos(0,0)
gs.set_color(0x1E)
gs.write("Hello World!")
gs.set_pos(2,1)
gs.set_color(0x8F)
gs.write("BLINKING TEXT")
gs.set_color(0x01)
gs.write("well, not if you're using gnome-terminal :(")
gs.set_color(0x78)
gs.draw_rect(10,5,70,20,"$")
gs.set_color(0x4B)
gs.fill_rect(8,7,73,19,".")
gs.set_cursor(40,3)
gs.flush()
time.sleep(0.5)
gs.repaint()
time.sleep(0.5)

sys.stdout.write("\x1B[1;1H\x1B[0m\x1B[2J")
sys.stdout.flush()


