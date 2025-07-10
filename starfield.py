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
        self.default_speed = 0.02
        self.num_stars = 200
        self.running = True
        self.paused = False
        self.trails = True
        self.color_mode = True
        self.trail_buffer = deque(maxlen=8)  # Increased for smoother fading
        self.frame_buffer = None
        self.pulse_phase = 0
        self.warp_mode = False
        self.warp_timer = 0
        
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
        self.trail_buffer.clear()  # Clear trails on resize to prevent index errors
        self.clear_screen()
        
    def update_terminal_size(self):
        size = os.get_terminal_size()
        self.width = max(20, size.columns)  # Minimum width
        self.height = max(5, size.lines - 2)  # Minimum height
        
    def get_color(self, z):
        if not self.color_mode:
            return ''
            
        if z > 0.8:
            return '\033[38;5;238m'  # Very dark gray
        elif z > 0.6:
            return '\033[38;5;245m'  # Medium gray
        elif z > 0.4:
            return '\033[38;5;252m'  # Light gray
        elif z > 0.2:
            return '\033[38;5;226m'  # Yellow
        else:
            return '\033[38;5;51m'   # Cyan
            
    def get_trail_char(self, age):
        """Get progressively fading trail characters"""
        chars = ['·', '·', '·', '.', '.', ' ', ' ', ' ']
        return chars[min(age, len(chars) - 1)]
        
    def get_trail_color(self, age):
        """Get progressively fading trail colors"""
        if not self.color_mode:
            return ''
        colors = [
            '\033[38;5;245m',  # Medium gray
            '\033[38;5;241m',  # Darker gray
            '\033[38;5;238m',  # Even darker
            '\033[38;5;235m',  # Very dark
            '\033[38;5;233m',  # Almost black
            '',
            '',
            ''
        ]
        return colors[min(age, len(colors) - 1)]
            
    def clear_screen(self):
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()
        
    def draw_status(self):
        # Calculate available space
        basic_status = f"Speed: {self.speed:.3f} | Stars: {self.num_stars}"
        if self.warp_mode:
            state = "WARP MODE!"
        elif self.paused:
            state = "Paused"
        else:
            state = "Running"
        
        # Priority controls for small windows
        if self.width < 40:
            # Minimal display
            status_line = f"\033[{self.height + 2};1H\033[K{basic_status}"
        elif self.width < 60:
            # Add state
            status_line = f"\033[{self.height + 2};1H\033[K{basic_status} | {state}"
        elif self.width < 80:
            # Add basic controls
            status_line = f"\033[{self.height + 2};1H\033[K{basic_status} | {state} | Q:quit Space:pause"
        elif self.width < 120:
            # Add more controls
            trails_color = f"Trails: {'ON' if self.trails else 'OFF'} | Color: {'ON' if self.color_mode else 'OFF'}"
            status_line = f"\033[{self.height + 2};1H\033[K{basic_status} | {trails_color} | {state}"
            status_line += "\n\033[K↑↓:speed ←→:stars T:trails C:color W:warp Space:pause Q:quit"
        else:
            # Full display
            status = f"{basic_status} | Trails: {'ON' if self.trails else 'OFF'} | "
            status += f"Color: {'ON' if self.color_mode else 'OFF'} | {state}"
            controls = "↑↓(speed) ←→(stars) 1-5(density) T(trails) C(color) W(warp) R(reset) Space(pause) Q(quit)"
            status_line = f"\033[{self.height + 2};1H\033[K{status} | {controls}"
        
        sys.stdout.write(status_line)
        sys.stdout.flush()
        
    def draw(self):
        if self.width <= 0 or self.height <= 0:
            return
            
        buffer = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        colors = [['' for _ in range(self.width)] for _ in range(self.height)]
        
        # Draw trails with progressive fading
        if self.trails and self.trail_buffer:
            for age, (old_buffer, old_colors) in enumerate(self.trail_buffer):
                if len(old_buffer) == self.height and all(len(row) == self.width for row in old_buffer):
                    for y in range(min(self.height, len(old_buffer))):
                        for x in range(min(self.width, len(old_buffer[y]))):
                            if old_buffer[y][x] != ' ' and buffer[y][x] == ' ':
                                buffer[y][x] = self.get_trail_char(age)
                                colors[y][x] = self.get_trail_color(age)
        
        # Draw current stars
        for star in self.stars:
            x, y = star.get_screen_pos(self.width, self.height)
            if x is not None and y is not None:
                buffer[y][x] = star.get_char()
                colors[y][x] = self.get_color(star.z)
                
        # Add to trail buffer
        if self.trails:
            self.trail_buffer.append((
                [row[:] for row in buffer],
                [row[:] for row in colors]
            ))
        
        # Render the frame
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
        
        # Update pulse phase for future effects
        self.pulse_phase = (self.pulse_phase + 0.1) % (2 * 3.14159)
        
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
            elif key == 'w' or key == 'W':
                self.warp_mode = not self.warp_mode
                if self.warp_mode:
                    self.warp_timer = 100  # Warp for ~3 seconds
            elif key == 'r' or key == 'R':
                # Reset to defaults
                self.speed = self.default_speed
                self.num_stars = 200
                self.trails = True
                self.color_mode = True
                self.warp_mode = False
                # Adjust star count
                if len(self.stars) > self.num_stars:
                    self.stars = self.stars[:self.num_stars]
                else:
                    while len(self.stars) < self.num_stars:
                        self.stars.append(Star(
                            random.uniform(-1, 1),
                            random.uniform(-1, 1),
                            random.uniform(0.1, 1.0)
                        ))
            elif key in '12345':
                # Density presets
                densities = {'1': 50, '2': 100, '3': 200, '4': 350, '5': 500}
                self.num_stars = densities[key]
                if len(self.stars) > self.num_stars:
                    self.stars = self.stars[:self.num_stars]
                else:
                    while len(self.stars) < self.num_stars:
                        self.stars.append(Star(
                            random.uniform(-1, 1),
                            random.uniform(-1, 1),
                            random.uniform(0.1, 1.0)
                        ))
                
    def run(self):
        try:
            tty.setraw(sys.stdin.fileno())
            self.clear_screen()
            sys.stdout.write('\033[?25l')  # Hide cursor
            sys.stdout.flush()
            
            while self.running:
                self.check_input()
                
                if not self.paused:
                    # Handle warp mode
                    if self.warp_mode and self.warp_timer > 0:
                        current_speed = self.speed * 5  # 5x speed in warp
                        self.warp_timer -= 1
                        if self.warp_timer <= 0:
                            self.warp_mode = False
                    else:
                        current_speed = self.speed
                        
                    for star in self.stars:
                        star.update(current_speed)
                        
                self.draw()
                time.sleep(0.03)
                
        except KeyboardInterrupt:
            pass
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            sys.stdout.write('\033[?25h')  # Show cursor
            self.clear_screen()
            sys.stdout.write("Thanks for watching the stars! ✨\n")
            sys.stdout.flush()

if __name__ == "__main__":
    starfield = Starfield()
    starfield.run()