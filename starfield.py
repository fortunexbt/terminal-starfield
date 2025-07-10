#!/usr/bin/env python3
import sys
import time
import random
import os
import termios
import tty
import select
import signal
from collections import deque

class Star:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.prev_x = None
        self.prev_y = None
        
    def update(self, speed):
        self.z -= speed
        if self.z <= 0:
            self.reset()
            
    def reset(self):
        self.x = random.uniform(-1, 1)
        self.y = random.uniform(-1, 1)
        self.z = random.uniform(0.1, 1.0)
        self.prev_x = None
        self.prev_y = None
        
    def get_screen_pos(self, width, height):
        if self.z <= 0:
            return None, None
            
        screen_x = int((self.x / self.z + 1) * width / 2)
        screen_y = int((self.y / self.z + 1) * height / 2)
        
        if 0 <= screen_x < width and 0 <= screen_y < height:
            return screen_x, screen_y
        return None, None
        
    def get_char(self):
        if self.z > 0.8:
            return '.'
        elif self.z > 0.6:
            return '·'
        elif self.z > 0.4:
            return '○'
        elif self.z > 0.2:
            return '◉'
        else:
            return '⬤'

class Starfield:
    def __init__(self):
        self.stars = []
        self.speed = 0.02
        self.num_stars = 200
        self.running = True
        self.paused = False
        self.trails = True
        self.color_mode = True
        self.trail_buffer = deque(maxlen=5)
        self.frame_buffer = None
        
        self.update_terminal_size()
        signal.signal(signal.SIGWINCH, self.handle_resize)
        
        for _ in range(self.num_stars):
            star = Star(
                random.uniform(-1, 1),
                random.uniform(-1, 1),
                random.uniform(0.1, 1.0)
            )
            self.stars.append(star)
            
        self.old_settings = termios.tcgetattr(sys.stdin)
        
    def handle_resize(self, signum, frame):
        self.update_terminal_size()
        self.clear_screen()
        
    def update_terminal_size(self):
        size = os.get_terminal_size()
        self.width = size.columns
        self.height = size.lines - 2
        self.trail_buffer.clear()
        
    def get_color(self, z):
        if not self.color_mode:
            return ''
            
        if z > 0.8:
            return '\033[90m'
        elif z > 0.6:
            return '\033[37m'
        elif z > 0.4:
            return '\033[97m'
        elif z > 0.2:
            return '\033[93m'
        else:
            return '\033[96m'
            
    def clear_screen(self):
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()
        
    def draw_status(self):
        status = f"Speed: {self.speed:.3f} | Stars: {self.num_stars} | "
        status += f"Trails: {'ON' if self.trails else 'OFF'} | "
        status += f"Color: {'ON' if self.color_mode else 'OFF'} | "
        status += "Paused" if self.paused else "Running"
        
        controls = "↑↓(speed) ←→(stars) T(trails) C(color) Space(pause) Q(quit)"
        
        status_line = f"\033[{self.height + 2};1H\033[K{status}"
        if len(status) + len(controls) + 3 < self.width:
            status_line += f" | {controls}"
        
        sys.stdout.write(status_line)
        sys.stdout.flush()
        
    def draw(self):
        if self.width <= 0 or self.height <= 0:
            return
            
        buffer = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        colors = [['' for _ in range(self.width)] for _ in range(self.height)]
        
        if self.trails and self.trail_buffer:
            for old_buffer, old_colors in self.trail_buffer:
                if len(old_buffer) == self.height and all(len(row) == self.width for row in old_buffer):
                    for y in range(self.height):
                        for x in range(self.width):
                            if old_buffer[y][x] != ' ':
                                buffer[y][x] = '·'
                                colors[y][x] = '\033[90m'
        
        for star in self.stars:
            x, y = star.get_screen_pos(self.width, self.height)
            if x is not None and y is not None:
                buffer[y][x] = star.get_char()
                colors[y][x] = self.get_color(star.z)
                
        if self.trails:
            self.trail_buffer.append((
                [row[:] for row in buffer],
                [row[:] for row in colors]
            ))
        
        output = []
        output.append('\033[H')
        
        for y in range(self.height):
            output.append(f'\033[{y + 1};1H\033[K')
            line_parts = []
            for x in range(self.width):
                if buffer[y][x] != ' ':
                    line_parts.append(colors[y][x] + buffer[y][x] + '\033[0m')
                else:
                    line_parts.append(' ')
            output.append(''.join(line_parts))
            
        sys.stdout.write(''.join(output))
        self.draw_status()
        
    def check_input(self):
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            
            if key == 'q' or key == 'Q':
                self.running = False
            elif key == ' ':
                self.paused = not self.paused
            elif key == '\x1b':
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    if sys.stdin.read(1) == '[':
                        if select.select([sys.stdin], [], [], 0.01)[0]:
                            arrow = sys.stdin.read(1)
                            if arrow == 'A':
                                self.speed = min(0.1, self.speed + 0.005)
                            elif arrow == 'B':
                                self.speed = max(0.001, self.speed - 0.005)
                            elif arrow == 'C':
                                self.num_stars = min(500, self.num_stars + 10)
                                for _ in range(10):
                                    self.stars.append(Star(
                                        random.uniform(-1, 1),
                                        random.uniform(-1, 1),
                                        random.uniform(0.1, 1.0)
                                    ))
                            elif arrow == 'D':
                                self.num_stars = max(10, self.num_stars - 10)
                                if len(self.stars) > self.num_stars:
                                    self.stars = self.stars[:self.num_stars]
            elif key == 't' or key == 'T':
                self.trails = not self.trails
                self.trail_buffer.clear()
            elif key == 'c' or key == 'C':
                self.color_mode = not self.color_mode
                
    def run(self):
        try:
            tty.setraw(sys.stdin.fileno())
            self.clear_screen()
            sys.stdout.write('\033[?25l')
            sys.stdout.flush()
            
            while self.running:
                self.check_input()
                
                if not self.paused:
                    for star in self.stars:
                        star.update(self.speed)
                        
                self.draw()
                time.sleep(0.03)
                
        except KeyboardInterrupt:
            pass
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            sys.stdout.write('\033[?25h')
            self.clear_screen()
            sys.stdout.write("Thanks for watching the stars! ✨\n")
            sys.stdout.flush()

if __name__ == "__main__":
    starfield = Starfield()
    starfield.run()