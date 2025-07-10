import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque
import re

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Cola de reproducción
music_queue = deque()
is_playing = False
voice_client = None

# Configuración de yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Es una playlist
            return [cls(discord.FFmpegPCMAudio(entry['url'], **ffmpeg_options), data=entry) 
                    for entry in data['entries'] if entry]
        else:
            # Es un video individual
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return [cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)]

@bot.event
async def on_ready():
    print(f'{bot.user} se ha conectado a Discord!')
    await bot.change_presence(activity=discord.Game(name="🎵 !help para comandos"))

@bot.command(name='join', help='Une el bot al canal de voz')
async def join(ctx):
    global voice_client
    if not ctx.message.author.voice:
        await ctx.send("❌ Debes estar en un canal de voz para usar este comando!")
        return

    channel = ctx.message.author.voice.channel
    voice_client = await channel.connect()
    await ctx.send(f"✅ Conectado a {channel}")

@bot.command(name='leave', help='Desconecta el bot del canal de voz')
async def leave(ctx):
    global voice_client, is_playing
    if voice_client:
        is_playing = False
        music_queue.clear()
        await voice_client.disconnect()
        voice_client = None
        await ctx.send("👋 Desconectado del canal de voz")
    else:
        await ctx.send("❌ No estoy conectado a ningún canal de voz")

@bot.command(name='play', help='Reproduce música desde YouTube (URL o búsqueda)')
async def play(ctx, *, url):
    global voice_client, is_playing

    if not voice_client:
        if ctx.message.author.voice:
            channel = ctx.message.author.voice.channel
            voice_client = await channel.connect()
        else:
            await ctx.send("❌ Debes estar en un canal de voz o usar !join primero")
            return

    async with ctx.typing():
        try:
            # Verificar si es una URL válida de YouTube
            if not re.match(r'https?://(www\.)?(youtube|youtu\.be)', url):
                url = f"ytsearch:{url}"

            sources = await YTDLSource.from_url(url, loop=bot.loop, stream=True)

            for source in sources:
                music_queue.append((source, ctx))

            if len(sources) == 1:
                await ctx.send(f"🎵 Agregado a la cola: **{sources[0].title}**")
            else:
                await ctx.send(f"📋 Agregadas {len(sources)} canciones a la cola")

            if not is_playing:
                await play_next(ctx)

        except Exception as e:
            await ctx.send(f"❌ Error al procesar: {str(e)}")

async def play_next(ctx):
    global is_playing, voice_client

    if not music_queue:
        is_playing = False
        return

    is_playing = True
    source, original_ctx = music_queue.popleft()

    def after_playing(error):
        if error:
            print(f'Error en reproducción: {error}')
        asyncio.run_coroutine_threadsafe(play_next(original_ctx), bot.loop)

    voice_client.play(source, after=after_playing)
    await ctx.send(f"🎶 Reproduciendo: **{source.title}**")

@bot.command(name='skip', help='Salta la canción actual')
async def skip(ctx):
    global voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭️ Canción saltada")
    else:
        await ctx.send("❌ No hay música reproduciéndose")

@bot.command(name='queue', help='Muestra la cola de reproducción')
async def queue_command(ctx):
    if not music_queue:
        await ctx.send("📭 La cola está vacía")
        return

    queue_list = []
    for i, (source, _) in enumerate(list(music_queue)[:10], 1):
        queue_list.append(f"{i}. {source.title}")

    embed = discord.Embed(
        title="🎵 Cola de Reproducción",
        description="\n".join(queue_list),
        color=0x00ff00
    )

    if len(music_queue) > 10:
        embed.set_footer(text=f"... y {len(music_queue) - 10} más")

    await ctx.send(embed=embed)

@bot.command(name='clear', help='Limpia la cola de reproducción')
async def clear(ctx):
    music_queue.clear()
    await ctx.send("🗑️ Cola limpiada")

@bot.command(name='pause', help='Pausa la reproducción')
async def pause(ctx):
    global voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ Música pausada")
    else:
        await ctx.send("❌ No hay música reproduciéndose")

@bot.command(name='resume', help='Reanuda la reproducción')
async def resume(ctx):
    global voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("▶️ Música reanudada")
    else:
        await ctx.send("❌ La música no está pausada")

@bot.command(name='stop', help='Detiene la música y limpia la cola')
async def stop(ctx):
    global voice_client, is_playing
    if voice_client:
        is_playing = False
        music_queue.clear()
        voice_client.stop()
        await ctx.send("⏹️ Música detenida y cola limpiada")
    else:
        await ctx.send("❌ No hay música reproduciéndose")

@bot.command(name='volume', help='Cambia el volumen (0-100)')
async def volume(ctx, volume: int):
    global voice_client
    if voice_client and voice_client.source:
        if 0 <= volume <= 100:
            voice_client.source.volume = volume / 100
            await ctx.send(f"🔊 Volumen cambiado a {volume}%")
        else:
            await ctx.send("❌ El volumen debe estar entre 0 y 100")
    else:
        await ctx.send("❌ No hay música reproduciéndose")

# Ejecutar el bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("❌ Error: No se encontró el token de Discord")
        print("Asegúrate de configurar la variable de entorno DISCORD_TOKEN")
    else:
        bot.run(TOKEN)
