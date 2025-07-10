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
import math

class Trail:
    def __init__(self, x, y, char, color, lifetime=10):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.lifetime = lifetime
        self.age = 0
        # Add slight variations to decay rate
        self.decay_rate = random.uniform(1.8, 2.5)
        
    def update(self):
        self.age += 1
        return self.age < self.lifetime
        
    def get_intensity(self):
        # Exponential decay for more natural fading with varied decay rate
        return max(0, 1.0 - (self.age / self.lifetime) ** self.decay_rate)

class Star:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.trail_positions = deque(maxlen=15)  # Store trail history per star
        self.trail_factor = random.uniform(0.5, 1.5)  # Random trail length multiplier
        
    def update(self, speed):
        # Store previous position for trails
        old_z = self.z
        self.z -= speed
        
        if self.z <= 0:
            self.reset()
            self.trail_positions.clear()
            
    def reset(self):
        self.x = random.uniform(-1, 1)
        self.y = random.uniform(-1, 1)
        self.z = random.uniform(0.8, 1.0)  # Start further away
        
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
        self.trails_list = []  # Individual trail objects
        self.frame_time = 0.016  # 60 FPS
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
        self.trails_list.clear()  # Clear trails on resize
        self.clear_screen()
        
    def update_terminal_size(self):
        size = os.get_terminal_size()
        self.width = max(20, size.columns)
        self.height = max(5, size.lines - 2)
        
    def get_color(self, z, intensity=1.0):
        if not self.color_mode:
            return ''
            
        # Apply intensity for fading
        if intensity < 0.2:
            return '\033[38;5;232m'  # Almost black
        elif intensity < 0.4:
            return '\033[38;5;234m'  # Very dark
        elif intensity < 0.6:
            return '\033[38;5;236m'  # Dark
        elif intensity < 0.8:
            return '\033[38;5;238m'  # Medium dark
        
        # Normal depth-based colors
        if z > 0.8:
            return '\033[38;5;240m'  # Dark gray
        elif z > 0.6:
            return '\033[38;5;245m'  # Medium gray
        elif z > 0.4:
            return '\033[38;5;250m'  # Light gray
        elif z > 0.2:
            return '\033[38;5;226m'  # Yellow
        else:
            return '\033[38;5;51m'   # Cyan
            
    def get_trail_char(self, intensity):
        """Get trail character based on intensity"""
        if intensity > 0.8:
            return '·'
        elif intensity > 0.5:
            return '.'
        elif intensity > 0.3:
            # Sometimes use a different character for variety
            return '.' if random.random() < 0.7 else '·'
        elif intensity > 0.1:
            return '.'
        else:
            return ' '
            
    def clear_screen(self):
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()
        
    def draw_status(self):
        basic_status = f"Speed: {self.speed:.3f} | Stars: {self.num_stars}"
        if self.warp_mode:
            state = "WARP MODE!"
        elif self.paused:
            state = "Paused"
        else:
            state = "Running"
        
        # Adaptive display based on width
        if self.width < 40:
            status_line = f"\033[{self.height + 2};1H\033[K{basic_status}"
        elif self.width < 60:
            status_line = f"\033[{self.height + 2};1H\033[K{basic_status} | {state}"
        elif self.width < 80:
            status_line = f"\033[{self.height + 2};1H\033[K{basic_status} | {state} | Q:quit Space:pause"
        elif self.width < 120:
            trails_color = f"Trails: {'ON' if self.trails else 'OFF'} | Color: {'ON' if self.color_mode else 'OFF'}"
            status_line = f"\033[{self.height + 2};1H\033[K{basic_status} | {trails_color} | {state}"
            status_line += "\n\033[K↑↓:speed ←→:stars T:trails C:color W:warp Space:pause Q:quit"
        else:
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
        
        # Update and draw trails
        if self.trails:
            # Update existing trails
            self.trails_list = [trail for trail in self.trails_list if trail.update()]
            
            # Draw trails with proper fading
            for trail in self.trails_list:
                if 0 <= trail.x < self.width and 0 <= trail.y < self.height:
                    intensity = trail.get_intensity()
                    if intensity > 0:
                        char = self.get_trail_char(intensity)
                        if char != ' ':
                            buffer[trail.y][trail.x] = char
                            colors[trail.y][trail.x] = self.get_color(0.5, intensity)
        
        # Draw current stars and create new trails
        for star in self.stars:
            x, y = star.get_screen_pos(self.width, self.height)
            if x is not None and y is not None:
                # Add trail at previous position
                if self.trails and len(star.trail_positions) > 0:
                    prev_x, prev_y = star.trail_positions[-1]
                    if (prev_x != x or prev_y != y) and 0 <= prev_x < self.width and 0 <= prev_y < self.height:
                        # Adjust trail lifetime based on speed and star's random factor
                        base_lifetime = int(12 / (1 + self.speed * 20))  # Slightly longer base
                        trail_lifetime = int(base_lifetime * star.trail_factor)
                        trail_lifetime = max(2, min(20, trail_lifetime))  # Clamp between 2-20
                        
                        if self.warp_mode:
                            trail_lifetime = max(3, trail_lifetime // 2)
                        
                        # Add some randomness to trail creation (not every frame)
                        if random.random() < 0.9:  # 90% chance to create trail
                            # Only add trail if we're not at max capacity
                            if len(self.trails_list) < 1000:  # Limit trails to prevent lag
                                self.trails_list.append(Trail(
                                    prev_x, prev_y, 
                                    '·', 
                                    self.get_color(star.z),
                                    trail_lifetime
                                ))
                
                # Store current position
                star.trail_positions.append((x, y))
                
                # Draw star
                buffer[y][x] = star.get_char()
                colors[y][x] = self.get_color(star.z)
        
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
                self.trails_list.clear()
                for star in self.stars:
                    star.trail_positions.clear()
            elif key == 'c' or key == 'C':
                self.color_mode = not self.color_mode
            elif key == 'w' or key == 'W':
                self.warp_mode = not self.warp_mode
                if self.warp_mode:
                    self.warp_timer = 60  # Shorter warp duration
                    # Clear old trails for cleaner warp effect
                    self.trails_list = [t for t in self.trails_list if t.age < 2]
            elif key == 'r' or key == 'R':
                # Reset to defaults
                self.speed = self.default_speed
                self.num_stars = 200
                self.trails = True
                self.color_mode = True
                self.warp_mode = False
                self.trails_list.clear()
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
                        current_speed = self.speed * 3  # Reduced from 5x to 3x
                        self.warp_timer -= 1
                        if self.warp_timer <= 0:
                            self.warp_mode = False
                    else:
                        current_speed = self.speed
                        
                    for star in self.stars:
                        star.update(current_speed)
                        
                self.draw()
                time.sleep(self.frame_time)  # 60 FPS
                
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