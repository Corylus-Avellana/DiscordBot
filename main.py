#!/usr/bin/env python
import discord
import mariadb
from discord.ext import commands, tasks

import os
import logging
import asyncio
import time
import math
import sys

token = os.environ['DISCORD_TOKEN']


logging.basicConfig(level=logging.INFO)


#connect to db
try:
    conn = mariadb.connect(
        user= os.environ['MARIADB_USER'],
        password= os.environ["MARIADB_PW"],
        host= os.environ["MARIADB_HOST"],
        port= int(os.environ["MARIADB_PORT"]),
        database= os.environ["MARIADB_DISCORDBOT_DB"]
    )
    logging.info("mariadb is ready")

except mariadb.Error as e:
    logging.error("Error connecting to MariaDB Platform: " + str(e))
    sys.exit(1)

#get cursor for db
cur = conn.cursor()
client = commands.Bot(command_prefix="$")

@client.event
async def on_ready():
    logging.info(client.user.name + " is ready")

class Announcer(commands.Cog):
    def __init__(self, client, cur, conn):
        self.client = client
        self.cur = cur
        self.conn = conn
        #an array for storing all announce tasks
        self.queue = []
        self.refreshtime = 500
        self.lastrefresh = 0

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.refresh.is_running():
            self.refresh.start()

    @commands.Cog.listener()
    async def on_command_error(self, ctx, e):
        if isinstance(e, commands.MissingRequiredArgument):
            await ctx.channel.send("<@" + str(ctx.message.author.id) + ">" + "Missing Required Arguements")

        if isinstance(e, commands.TooManyArguments):
            await ctx.channel.send("<@" + str(ctx.message.author.id) + ">" + "Too Many Arguments")
        else:
            await ctx.channel.send("<@" + str(ctx.message.author.id) + ">" + "Something has gone very wrong")
            raise e


    @tasks.loop (seconds = 500)
    async def refresh(self):
        self.lastrefresh = math.floor(time.time())
        cur.execute("SELECT id FROM Announce WHERE time <= ?", (math.floor(time.time()) + self.refreshtime,))
        ids = cur.fetchall()
        for i in range(len(self.queue)):
            #cancels all tasks if there are any
            self.queue[i].cancel()
        self.queue = []
        newtasks = []
        for i in range(cur.rowcount):
            #recreates all tasks from db if there are any
            newtasks.append(asyncio.create_task(self.announce_vote_task(ids[i][0])))
        asyncio.gather(*tuple(newtasks))


    @commands.command(name="prepmessage")
    async def prep_message(self, ctx, sendat, ping, channel, threshold, text):
        try:
            #get channel id
            channel = channel[2:-1]
            #check channel id is within guild
            if ctx.guild.get_channel(int(channel)) is None:
                await ctx.channel.send("<@" + str(ctx.message.author.id) + ">" + "Channel does not exist")
                return
        except ValueError:
            await ctx.channel.send("<@" + str(ctx.message.author.id) + ">" + "Channel is invalid format")
            return

        react = await ctx.channel.send(f"""
Attention, {ping} \n <@{ctx.message.author.id}> would like to send
\"
{text}
\"
<t:{sendat}> to <#{channel}> requires {threshold} votes"""
        )
        await react.add_reaction("👍")
        await react.add_reaction("👎")

        sendat = int(sendat)
        cur.execute("INSERT INTO Announce(time, channelid, text, react_msg, guildid, react_chan, threshold)" 
                    + "VALUES (?, ?, ?, ?, ?, ?, ?)", 
                    (sendat, channel, text, react.id, ctx.guild.id, react.channel.id, threshold,))
        conn.commit()
        #Creates new task to announce message if within refreshtime
        if sendat <= self.lastrefresh + self.refreshtime:
            await self.announce_vote_task(cur.lastrowid)

    async def announce_vote_task(self, id):
        task = asyncio.create_task(self.announce_vote(id))
        self.queue.append(task)
        await task
        try:
            self.queue.remove(task)
        except:
            logging.info(str(id) + " already removed")

    async def announce_vote(self, id):
        try:
            cur.execute("select time from Announce where id=?", (id,))
            when = cur.fetchone()[0]
            sendin = int(when) - math.floor(time.time())

            if sendin >= 0:
                await asyncio.sleep(sendin)

            cur.execute("SELECT time, channelid, react_msg, text, guildid, react_chan, threshold FROM  Announce WHERE id=?", 
                    (id,))
            message = cur.fetchone()
            if message[0] <= math.floor(time.time()) + 1:
                guild = client.get_guild(int(message[4]))
                sendchannel = guild.get_channel(int(message[1]))
                reactchan = guild.get_channel(int(message[5]))
                reactmsg = await reactchan.fetch_message(int(message[2]))
                if reactmsg.reactions[0].count - reactmsg.reactions[1].count >= message[6]:
                    await sendchannel.send(message[3])
                    cur.execute("DELETE FROM Announce where id=?", (id,))
                    conn.commit()
                    await reactmsg.add_reaction("✅")

                else:
                    cur.execute("DELETE FROM Announce where id=?", (id,))
                    conn.commit()
                    await reactmsg.add_reaction("❌")

        except asyncio.CancelledError:
            pass


client.add_cog(Announcer(client, cur, conn))
client.run(token)
