# Terminal Starfield

A mesmerizing 3D starfield animation for your terminal with real-time controls and visual effects.

![Python Version](https://img.shields.io/badge/python-3.6%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Terminal](https://img.shields.io/badge/terminal-ready-brightgreen)

## Overview

Terminal Starfield transforms your command line into a window to the cosmos. Watch as stars rush past in a stunning 3D simulation, complete with depth perception, motion trails, and customizable effects. Perfect for adding some visual flair to your terminal or just taking a moment to relax and watch the stars.

## Features

### 🌟 Visual Effects
- **3D Depth Simulation**: Stars appear smaller when distant and grow as they approach
- **Motion Trails**: Toggle ethereal trails for a warp-speed effect
- **Dynamic Characters**: Star appearance changes based on distance (. · ○ ◉ ⬤)
- **Color Gradients**: Optional color mode with distance-based coloring

### 🎮 Real-Time Controls
- **↑/↓ Arrow Keys**: Adjust animation speed
- **←/→ Arrow Keys**: Add or remove stars (10-500 stars)
- **Spacebar**: Pause/resume animation
- **T**: Toggle motion trails on/off
- **C**: Toggle color mode on/off
- **Q**: Quit the application

### 🚀 Performance
- Optimized rendering with buffer management
- Smooth 30 FPS animation
- Responsive controls with no lag
- Automatic terminal size detection

## Installation

### Prerequisites
- Python 3.6 or higher
- A terminal that supports Unicode characters
- A terminal that supports ANSI color codes (most modern terminals)

### Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/terminal-starfield.git
cd terminal-starfield
```

2. Run the starfield:
```bash
python3 starfield.py
```

That's it! No external dependencies required.

## Usage

Simply run the script and use the keyboard controls to customize your experience:

```bash
./starfield.py
# or
python3 starfield.py
```

### Control Reference

| Key | Action |
|-----|--------|
| ↑ | Increase speed |
| ↓ | Decrease speed |
| ← | Remove 10 stars |
| → | Add 10 stars |
| Space | Pause/Resume |
| T | Toggle trails |
| C | Toggle colors |
| Q | Quit |

## Technical Details

### How It Works

The starfield uses a simple 3D to 2D projection algorithm:
- Each star has X, Y, and Z coordinates
- Z represents depth (0 = close, 1 = far)
- Stars are projected onto the 2D terminal screen based on their position
- As Z decreases, stars appear to move outward from the center

### Terminal Compatibility

The application uses standard ANSI escape codes and should work on:
- Linux terminals (GNOME Terminal, Konsole, xterm, etc.)
- macOS Terminal and iTerm2
- Windows Terminal
- Most SSH clients

### Performance Considerations

- Default: 200 stars at 30 FPS
- Minimal CPU usage through efficient buffer management
- Automatic cleanup on exit (cursor restored, screen cleared)

## Customization

You can easily modify the starfield by editing these variables in `starfield.py`:

```python
self.speed = 0.02        # Initial animation speed
self.num_stars = 200     # Starting number of stars
self.trails = True       # Enable trails by default
self.color_mode = True   # Enable colors by default
```

## Contributing

Feel free to open issues or submit pull requests! Some ideas for contributions:
- Additional visual effects
- Configuration file support
- Different star movement patterns
- Screenshot/recording functionality

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Inspired by classic screensavers and the beauty of space. Built with pure Python using only standard library modules.

---

*Enjoy your journey through the stars!* ✨