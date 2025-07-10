<div align="center">

# ✨ Terminal Starfield

### Journey through the cosmos from your command line

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.6%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Terminal](https://img.shields.io/badge/Terminal-Ready-brightgreen?logo=windowsterminal&logoColor=white)](https://github.com/fortunexbt/terminal-starfield)
[![Stars](https://img.shields.io/github/stars/fortunexbt/terminal-starfield?style=social)](https://github.com/fortunexbt/terminal-starfield/stargazers)

<img src="https://s7.ezgif.com/tmp/ezgif-7b31887f914c82.gif" alt="Terminal Starfield Demo" />

*A mesmerizing 3D starfield simulation with real-time controls and visual effects*

</div>

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/fortunexbt/terminal-starfield.git
cd terminal-starfield

# Run the starfield
python3 starfield.py
```

That's it! No dependencies required - just Python 3.6+ and a modern terminal.

## 🎯 Features

<table>
<tr>
<td width="50%">

### 🌌 Visual Effects
- **3D Depth Perception** - Stars grow as they approach
- **Progressive Trail Fading** - Realistic motion blur
- **Dynamic Characters** - Distance-based rendering
- **256-Color Gradients** - Smooth color transitions
- **Warp Mode** - Hyperspace speed burst effect

</td>
<td width="50%">

### ⚡ Performance
- **60 FPS** smooth animation
- **Zero Dependencies** - Pure Python stdlib
- **Optimized Rendering** - Efficient buffer management
- **Smart Resizing** - Handles terminal resize gracefully
- **Adaptive UI** - Status bar adjusts to window size

</td>
</tr>
</table>

## 🎮 Controls

<div align="center">

| Key | Action | Description |
|:---:|:-------|:------------|
| <kbd>↑</kbd> <kbd>↓</kbd> | Speed Control | Adjust animation speed |
| <kbd>←</kbd> <kbd>→</kbd> | Star Density | Add/remove 10 stars |
| <kbd>1</kbd>-<kbd>5</kbd> | Quick Presets | 50, 100, 200, 350, 500 stars |
| <kbd>Space</kbd> | Pause/Resume | Freeze the animation |
| <kbd>W</kbd> | 🚀 Warp Mode | 5x speed boost! |
| <kbd>T</kbd> | Toggle Trails | Motion blur on/off |
| <kbd>C</kbd> | Toggle Colors | Monochrome/color mode |
| <kbd>R</kbd> | Reset | Restore defaults |
| <kbd>Q</kbd> | Quit | Exit gracefully |

</div>

## 📸 Screenshots

<details>
<summary><b>Click to view screenshots</b></summary>

### Default View
```
                    ·                                      ○
      ·                            ·              
                ·        ◉                    ·
    ○                                  ·
              ·              ⬤                    ○
                                          ·
Speed: 0.020 | Stars: 200 | Trails: ON | Color: ON | Running
```

### Warp Mode Active
```
════════════○═══════════════════════◉═══════════════════
═══════⬤══════════════════○═════════════════════════════
═════════════════◉══════════════════════⬤═══════════════
Speed: 0.020 | Stars: 200 | Trails: ON | Color: ON | WARP MODE!
```

</details>

## 🛠️ Configuration

### Customize Your Experience

```python
# In starfield.py, modify these values:
self.speed = 0.02        # Default animation speed
self.num_stars = 200     # Starting star count
self.trails = True       # Enable trails by default
self.color_mode = True   # Enable colors by default
```

### Terminal Requirements

<table>
<tr>
<th>Feature</th>
<th>Requirement</th>
<th>Check Command</th>
</tr>
<tr>
<td>Unicode Support</td>
<td>UTF-8 encoding</td>
<td><code>echo $LANG</code></td>
</tr>
<tr>
<td>256 Colors</td>
<td>Modern terminal</td>
<td><code>tput colors</code></td>
</tr>
<tr>
<td>ANSI Escape Codes</td>
<td>VT100 compatible</td>
<td><code>echo -e "\033[31mRed\033[0m"</code></td>
</tr>
</table>

## 🎨 How It Works

<details>
<summary><b>Technical Implementation</b></summary>

### Core Algorithm

```python
# 3D to 2D Projection
screen_x = (star.x / star.z + 1) * width / 2
screen_y = (star.y / star.z + 1) * height / 2

# Z-depth determines:
# - Character size: . · ○ ◉ ⬤
# - Color brightness: darker when distant
# - Trail persistence: fading over time
```

### Key Components

1. **Star Class**: Manages individual star positions and movement
2. **Trail Buffer**: Deque storing previous frames for motion blur
3. **Signal Handling**: Graceful terminal resize via SIGWINCH
4. **Raw Mode Input**: Non-blocking keyboard input processing

</details>

## 🌟 What's New

### v2.0.0 - Enhanced Visual Experience
- ✨ Progressive trail fading with 8-frame buffer
- 🚀 Warp mode for hyperspace effects
- 🎨 Enhanced 256-color palette
- 📐 Smart window resize handling
- ⌨️ Number key density presets
- 🔄 Reset function

### Coming Soon
- [ ] Configuration file support
- [ ] Different motion patterns
- [ ] Performance metrics display
- [ ] Screenshot capture mode

## 🤝 Contributing

Contributions are welcome! Here are some ways you can help:

<table>
<tr>
<td>

### 🐛 Report Issues
Found a bug? [Open an issue](https://github.com/fortunexbt/terminal-starfield/issues/new) with:
- Terminal and OS info
- Steps to reproduce
- Expected vs actual behavior

</td>
<td>

### 💡 Feature Ideas
Have a suggestion? We'd love to hear it!
- Visual effects
- New controls
- Performance improvements
- Documentation

</td>
</tr>
</table>

### Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/terminal-starfield.git
cd terminal-starfield

# Create a branch
git checkout -b feature/amazing-feature

# Make changes and test
python3 starfield.py

# Commit and push
git add .
git commit -m "Add amazing feature"
git push origin feature/amazing-feature
```

## 📋 Compatibility

<div align="center">

| Platform | Terminal | Status |
|:---------|:---------|:------:|
| **Linux** | GNOME Terminal, Konsole, xterm | ✅ |
| **macOS** | Terminal.app, iTerm2 | ✅ |
| **Windows** | Windows Terminal, WSL | ✅ |
| **SSH** | PuTTY, OpenSSH | ✅ |

</div>

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

<div align="center">

Inspired by classic screensavers and the beauty of space.  
Built with ❤️ using only Python's standard library.

---

<sub>If you enjoy Terminal Starfield, please consider giving it a ⭐ on GitHub!</sub>

</div>
