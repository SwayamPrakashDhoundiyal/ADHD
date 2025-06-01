import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from cat_gifs import get_cat
from dotenv import load_dotenv
import webserver
import os
import time

# Set up logging
#logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Set up Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Timer class
class Timer:
    def __init__(self, time_set: int, invoke_func):
        self.time_set = time_set  # Time in seconds
        self.current_time_left = time_set
        self.pause_timer = False
        self.paused_time = 0
        self.timer_completed = False
        self.call_able = invoke_func

    async def start_timer(self):
        start_time = time.time()
        while self.current_time_left > 0 and not self.timer_completed:
            if not self.pause_timer:
                elapsed = time.time() - start_time
                self.current_time_left = max(0, self.time_set - elapsed)
            else:
                self.paused_time += 1
            await asyncio.sleep(1)  # Use asyncio.sleep for non-blocking delay
        
        if not self.timer_completed:
            self.timer_completed = True
            await self.call_able()  # Call the function asynchronously

    def pause_time(self):
        self.pause_timer = True

    def resume_time(self):
        self.pause_timer = False

# Discord bot class
class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='>', intents=intents)
        self.timers = {}  # Dictionary to store timers per guild

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        try:
            synced = await self.tree.sync()
            print(f'Synced {len(synced)} command(s)')
        except Exception as e:
            print(f'Failed to sync commands: {e}')

    async def mute_all_in_voice(self, guild: discord.Guild):
        """Mute all members in voice channels in the guild."""
        for channel in guild.voice_channels:
            for member in channel.members:
                try:
                    await member.edit(mute=True)
                except discord.Forbidden:
                    print(f'Cannot mute {member.name}: Missing permissions')
                    return False
                except Exception as e:
                    print(f'Error muting {member.name}: {e}')
                    return False
        return True

    async def unmute_all_in_voice(self, guild: discord.Guild):
        """Unmute all members in voice channels in the guild."""
        for channel in guild.voice_channels:
            for member in channel.members:
                try:
                    await member.edit(mute=False)
                except discord.Forbidden:
                    print(f'Cannot unmute {member.name}: Missing permissions')
                    return False
                except Exception as e:
                    print(f'Error unmuting {member.name}: {e}')
                    return False
        return True

client = Client()

@client.tree.command(name="set-timer", description="Set a timer (in seconds) and mute all users in voice channels. Unmutes when timer ends or is paused.")
@app_commands.describe(time="Time in seconds for the timer")
async def set_timer(interaction: discord.Interaction, time: int):
    """Set a timer and mute/unmute users in voice channels."""
    if time <= 0:
        await interaction.response.send_message("Please provide a positive time in seconds.", ephemeral=True)
        return

    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    # Check if a timer is already running in this guild
    if guild.id in client.timers:
        await interaction.response.send_message("A timer is already running in this server.", ephemeral=True)
        return

    # Mute all users in voice channels
    success = await client.mute_all_in_voice(guild)
    if not success:
        await interaction.response.send_message("Failed to mute some users due to permissions or errors.", ephemeral=True)
        return

    # Define the callback function to unmute users
    async def timer_callback():
        await client.unmute_all_in_voice(guild)
        channel = client.get_channel(client.channel)
        await channel.send("Timer completed! All users in voice channels have been unmuted.")
        client.timers.pop(guild.id, None)  # Remove timer from dictionary
        url = get_cat()
        await channel.send(url)

    # Create and start the timer
    timer = Timer(time, timer_callback)
    client.timers[guild.id] = timer
    channel_id = interaction.channel_id
    client.channel = channel_id

    # Send confirmation
    await interaction.response.send_message(f"Timer set for {time} seconds. All users in voice channels have been muted.")

    # Start the timer in the background
    client.loop.create_task(timer.start_timer())

@client.tree.command(name="pause-timer", description="Pause the running timer in this server and unmute all users.")
async def pause_timer(interaction: discord.Interaction):
    """Pause the timer in the guild and unmute all users."""
    guild = interaction.guild
    if guild is None or guild.id not in client.timers:
        await interaction.response.send_message("No timer is running in this server.", ephemeral=True)
        return

    timer = client.timers[guild.id]
    if timer.pause_timer:
        await interaction.response.send_message("Timer is already paused.", ephemeral=True)
        return

    timer.pause_time()
    success = await client.unmute_all_in_voice(guild)
    if not success:
        await interaction.response.send_message("Timer paused, but failed to unmute some users due to permissions or errors.", ephemeral=True)
        return

    await interaction.response.send_message("Timer paused. All users in voice channels have been unmuted.")

@client.tree.command(name="resume-timer", description="Resume the paused timer in this server and mute all users.")
async def resume_timer(interaction: discord.Interaction):
    """Resume the paused timer in the guild and mute all users."""
    guild = interaction.guild
    if guild is None or guild.id not in client.timers:
        await interaction.response.send_message("No timer is running in this server.", ephemeral=True)
        return

    timer = client.timers[guild.id]
    if not timer.pause_timer:
        await interaction.response.send_message("Timer is not paused.", ephemeral=True)
        return

    success = await client.mute_all_in_voice(guild)
    if not success:
        await interaction.response.send_message("Failed to mute some users due to permissions or errors.", ephemeral=True)
        return

    timer.resume_time()
    await interaction.response.send_message("Timer resumed. All users in voice channels have been muted.")
    await interaction.followup.send(f"After {timer.paused_time}(s)")

# Run the bot
webserver.keep_alive()
client.run(TOKEN)
