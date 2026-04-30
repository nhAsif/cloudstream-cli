import asyncio
import collections
import collections.abc
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Monkeypatch for Python 3.10+ compatibility with old python-inquirer
if not hasattr(collections, 'Mapping'):
    collections.Mapping = collections.abc.Mapping
if not hasattr(collections, 'MutableMapping'):
    collections.MutableMapping = collections.abc.MutableMapping
if not hasattr(collections, 'Sequence'):
    collections.Sequence = collections.abc.Sequence

try:
    from python_inquirer import prompt
except ImportError:
    # Fallback if python_inquirer is not available or correctly named
    def prompt(questions):
        print("Interactive prompt not available. Please provide more arguments.")
        return {}

from cloudstream_cli.orchestrator import get_manager
from cloudstream_cli.models import TvType, LoadResponse, Episode, ExtractorLink, SubtitleFile
from cloudstream_cli.player import Player

app = typer.Typer(help="CloudStream CLI - Search, Info, and Play media.")
console = Console()

async def search_logic(query: str):
    manager = get_manager()
    with console.status(f"[bold green]Searching for '{query}'..."):
        results = await manager.search(query)
    
    if not results:
        console.print("[bold red]No results found.[/bold red]")
        return

    choices = [f"{r.name} ({r.type.name if r.type else 'Unknown'}) - {r.apiName}" for r in results]
    choice_map = {choices[i]: results[i] for i in range(len(choices))}

    questions = [
        {
            'type': 'list',
            'name': 'result',
            'message': 'Select a result:',
            'choices': choices
        }
    ]
    answers = prompt(questions)
    if not answers or 'result' not in answers:
        return
    
    selected_choice = answers['result']
    selected_result = choice_map[selected_choice]
    
    await info_logic(selected_result.url)

async def info_logic(url: str):
    manager = get_manager()
    with console.status("[bold green]Loading details..."):
        details = await manager.load(url)
    
    if not details:
        console.print("[bold red]Failed to load details.[/bold red]")
        return
    
    console.print(Panel(
        f"[bold cyan]{details.name}[/bold cyan] ({details.year or 'N/A'})\n"
        f"[italic]{details.plot or 'No plot available.'}[/italic]\n\n"
        f"Type: {details.type.name} | Provider: {details.apiName}",
        title="Media Info",
        expand=False
    ))
    
    if hasattr(details, 'episodes') and details.episodes:
        # Sort episodes by season and episode number if possible
        sorted_episodes = sorted(
            details.episodes, 
            key=lambda x: (x.season or 0, x.episode or 0)
        )
        
        table = Table(title="Episodes")
        table.add_column("S", style="cyan")
        table.add_column("E", style="cyan")
        table.add_column("Title", style="white")
        
        for ep in sorted_episodes:
            table.add_row(str(ep.season or "?"), str(ep.episode or "?"), ep.name or "Unknown")
        
        console.print(table)
        
        if details.type in [TvType.TvSeries, TvType.Anime, TvType.Cartoon]:
            choices = [f"S{e.season}E{e.episode}: {e.name}" for e in sorted_episodes]
            choice_map = {choices[i]: sorted_episodes[i] for i in range(len(choices))}
            
            questions = [
                {
                    'type': 'list',
                    'name': 'episode',
                    'message': 'Select an episode to resolve links:',
                    'choices': choices + ["Cancel"]
                }
            ]
            answers = prompt(questions)
            if answers and answers.get('episode') != "Cancel":
                selected_episode = choice_map[answers['episode']]
                await play_logic(url, episode_data=selected_episode, details=details)
    else:
        # For movies or things without episodes
        questions = [
            {
                'type': 'list',
                'name': 'action',
                'message': 'Action:',
                'choices': ["Play", "Cancel"]
            }
        ]
        answers = prompt(questions)
        if answers and answers.get('action') == "Play":
            await play_logic(url, details=details)

async def play_logic(url: str, episode_n: Optional[int] = None, episode_data=None, details: LoadResponse = None):
    manager = get_manager()
    if not details:
        with console.status("[bold green]Loading details for playback..."):
            details = await manager.load(url)
    
    if not details:
        console.print("[bold red]Failed to load details.[/bold red]")
        return

    selected_episode_data = episode_data
    if not selected_episode_data and hasattr(details, 'episodes') and details.episodes:
        if episode_n is not None:
            for ep in details.episodes:
                if ep.episode == episode_n:
                    selected_episode_data = ep
                    break
        
        if not selected_episode_data:
            sorted_episodes = sorted(
                details.episodes, 
                key=lambda x: (x.season or 0, x.episode or 0)
            )
            choices = [f"S{e.season}E{e.episode}: {e.name}" for e in sorted_episodes]
            choice_map = {choices[i]: sorted_episodes[i] for i in range(len(choices))}
            questions = [
                {
                    'type': 'list',
                    'name': 'episode',
                    'message': 'Select an episode:',
                    'choices': choices
                }
            ]
            answers = prompt(questions)
            if answers:
                selected_episode_data = choice_map[answers['episode']]
    
    data_to_resolve = ""
    if selected_episode_data:
        data_to_resolve = selected_episode_data.data
        console.print(f"[bold green]Resolving links for Episode: {selected_episode_data.name}[/bold green]")
    elif hasattr(details, 'dataUrl'):
        data_to_resolve = details.dataUrl
        console.print(f"[bold green]Resolving links for Movie: {details.name}[/bold green]")
    else:
        # Try using the url itself if no specific dataUrl or episode data
        data_to_resolve = details.url
        console.print(f"[bold yellow]No specific data URL found, attempting to resolve main URL: {details.url}[/bold yellow]")

    links_found = []
    subs_found = []

    def link_callback(link: ExtractorLink):
        links_found.append(link)
        console.print(f"[bold blue]LINK:[/bold blue] {link.name} ({link.type.value}) - [underline]{link.url}[/underline]")

    def sub_callback(sub: SubtitleFile):
        subs_found.append(sub)
        console.print(f"[bold magenta]SUB:[/bold magenta] {sub.lang} - [underline]{sub.url}[/underline]")

    with console.status("[bold green]Resolving links..."):
        await manager.resolve_links(data_to_resolve, details.apiName, link_callback, sub_callback)
    
    if not links_found:
        console.print("[bold yellow]No links were resolved. Note: Some providers (like TMDB) only provide metadata.[/bold yellow]")
    else:
        console.print(f"\n[bold green]Successfully resolved {len(links_found)} links and {len(subs_found)} subtitles.[/bold green]")
        
        choices = [f"{link.name} ({link.source}) - {link.url[:50]}..." for link in links_found]
        choice_map = {choices[i]: links_found[i] for i in range(len(choices))}
        
        questions = [
            {
                'type': 'list',
                'name': 'link',
                'message': 'Select a link to play:',
                'choices': choices + ["Cancel"]
            }
        ]
        answers = prompt(questions)
        if answers and answers.get('link') != "Cancel":
            selected_link = choice_map[answers['link']]
            Player().play(selected_link, subs_found)

@app.command()
def search(query: str):
    """Search for movies and TV shows across all providers."""
    asyncio.run(search_logic(query))

@app.command()
def info(url: str):
    """Get detailed information about a movie or TV show from its URL."""
    asyncio.run(info_logic(url))

@app.command()
def play(url: str, episode: Optional[int] = typer.Option(None, "--episode", "-e", help="Episode number to play (for TV shows)")):
    """Resolve and display playback links for a given media URL."""
    asyncio.run(play_logic(url, episode_n=episode))

if __name__ == "__main__":
    app()
