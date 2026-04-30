# CloudStream CLI

A powerful Command Line Interface for searching, viewing information, and playing media from various online providers. Built with Python, it offers a seamless way to interact with the CloudStream ecosystem directly from your terminal.

## 🚀 Features

- **Multi-Provider Search**: Search for movies and TV shows across multiple providers simultaneously.
- **Detailed Information**: View plots, release years, ratings, and cast information.
- **Episode Management**: Browse seasons and episodes for TV shows and Anime.
- **Link Resolution**: Automatically resolve playback links and subtitles using various extractors.
- **Interactive UI**: User-friendly interactive prompts for selection.
- **Extension Support**: Easily add new providers by dropping Python scripts into the `extensions/` folder.
- **Rich Output**: Beautifully formatted tables and panels using the `rich` library.

## 🛠️ Installation

### Prerequisites

- Python 3.10 or higher
- [mpv](https://mpv.io/) (recommended for playback) or another media player.

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/nhAsif/cloudstream-cli.git
   cd cloudstream-cli
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 📖 Usage

Run the CLI using `python main.py`.

### Search for Media

Search for any movie or TV show:
```bash
python main.py search "Inception"
```

### View Media Info

Get details about a specific media using its TMDB or provider URL:
```bash
python main.py info "https://www.themoviedb.org/movie/27205-inception"
```

### Play Content

Resolve links and play content:
```bash
python main.py play "https://www.themoviedb.org/movie/27205-inception"
```
For TV shows, you can specify an episode:
```bash
python main.py play "https://www.themoviedb.org/tv/1396-breaking-bad" --episode 1
```

## 🧩 Extensions

CloudStream CLI supports dynamic extension loading. To add a new provider:
1. Create a Python script in the `extensions/` directory.
2. Define a class that inherits from `MainAPI`.
3. The CLI will automatically detect and register it on startup.

## 📦 Dependencies

- `httpx`: Modern HTTP client for Python.
- `typer`: For building the CLI interface.
- `rich`: For beautiful terminal formatting.
- `python-inquirer`: For interactive selection menus.
- `selectolax`: Fast HTML parsing.
- `pycryptodome`: Cryptographic primitives for link extraction.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
