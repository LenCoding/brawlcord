# Standard Library
import asyncio
import json
import logging
import random
import time
from typing import Optional

# Discord
import discord

# Redbot
from redbot.core import Config, commands, checks
from redbot.core.commands.context import Context
from redbot.core.data_manager import bundled_data_path
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.common_filters import filter_various_mentions
from redbot.core.utils.menus import (DEFAULT_CONTROLS, menu,
                                     start_adding_reactions)
# from redbot.core.utils.chat_formatting import box
from redbot.core.utils.predicates import ReactionPredicate

from .brawlers import emojis, brawler_emojis, Brawler, Shelly, Nita, Colt


BaseCog = getattr(commands, "Cog", object)

log = logging.getLogger("red.brawlcord")

__version__ = "1.0.0"
__author__ = "Snowsee"

default_stats = {
    "trophies": 0,
    "pb": 0,
    "level": 1,
    "powerpoints": 0,
    "skins": ["Default"],
    "sp1": False,
    "sp2": False
}

default_user = {
    "xp": 0,
    "gold": 0,
    "lvl": 1,
    "starpoints": 0,
    "startokens": 0,
    "tokens": 0,
    "tokens_in_bank": 200,
    # "trophies": 0,
    "tutorial_finished": False,
    "brawlers": {
        "Shelly": default_stats
    },
    "gamemodes": [
        "Gem Grab"
    ],
    "selected": {
        "brawler": "Shelly",
        "brawler_skin": "Default",
        "gamemode": "Gem Grab",
        "starpower": None
    }
}

brawlers_map = {
    "Shelly": Shelly,
    "Nita": Nita,
    "Colt": Colt
}

# tutorial_trophies = 10

imgur_links = {
    "shelly_tut": "https://i.imgur.com/QfKYzso.png"
}


gamemode_emotes = {
    "Big Game": "<:big_game:645925169344282624>",
    "Bounty": "<:bounty:645925169252270081>",
    "Boss Fight": "<:bossfight:645925170397052929>",
    "Brawl Ball": "<:brawlball:645925169650466816>",
    "Gem Grab": "<:gemgrab:645925169730289664>",
    "Duo Showdown": "<:duo_showdown:645925169805656076>",
    "Heist": "<:heist:645925170195988491>",
    "raid": "<:raid:645925170397052929>",
    "Siege": "<:siege:645925170481201163>",
    "Solo Showdown": "<:solo_showdown:645925170539921428>",
    "Robo Rumble": "<:roborumble:645925170594316288>",
    "Lone Star": "<:lonestar:645925170610962452>",
    "Takedown": "<:takedown:645925171034587146>",
}

class BrawlCord(BaseCog, name="BrawlCord"):
    """Simulate Brawl Stars."""

    def __init__(self, bot):
        self.bot = bot

        # self._brawl_countdown = {}
        self.sessions = {}
        self.tasks = {}
        self.locks = {}

        self.config = Config.get_conf(
            self, 1_070_701_001, force_registration=True)

        self.path = bundled_data_path(self)

        self.config.register_user(**default_user)

        self.BRAWLERS: dict = None
        self.REWARDS: dict = None
        self.XP_LEVELS: dict = None

    async def initialize(self):
        brawlers_fp = bundled_data_path(self) / "brawlers.json"
        rewards_fp = bundled_data_path(self) / "rewards.json"
        xp_levels_fp = bundled_data_path(self) / "xp_levels.json"

        with brawlers_fp.open("r") as f:
            self.BRAWLERS = json.load(f)
        with rewards_fp.open("r") as f:
            self.REWARDS = json.load(f)
        with xp_levels_fp.open("r") as f:
            self.XP_LEVELS = json.load(f)

    @commands.command(name="brawl", aliases=["b"])
    @commands.guild_only()
    # @commands.cooldown(rate=1, per=60, type=commands.BucketType.guild)
    async def _brawl(
        self,
        ctx: Context,
        teammate1: discord.Member = None,
        teammate2: discord.Member = None
    ):
        """Brawl against others!"""

        author = ctx.author
        guild = ctx.guild

        tutorial_finished = await self.get_player_stat(author, "tutorial_finished")

        if not tutorial_finished:
            return await ctx.send(f"{author.mention} You have not finished tutorial yet."
                                  "Use  `-tutorial` to start tutorial.")

        teammates = [teammate1, teammate2]

        players = [author]

        for teammate in teammates:
            if teammate:
                if teammate == author:
                    return await ctx.send("You can't play with yourself!")
                elif teammate == guild.me:
                    return await ctx.send("I can't play!")
                players.append(teammate)

        # await ctx.send(teammates)

        results = {}

        for player in players:
            selected_brawler = (await self.get_player_stat(player, "selected"))["brawler"]

            user_brawler_level = (await self.get_player_stat(player, "brawlers"))[selected_brawler]["level"]

            opp_brawler, opp_brawler_level, opp_brawler_sp = self.matchmaking(
                user_brawler_level)

            user1: Brawler = brawlers_map[selected_brawler](
                self.BRAWLERS, selected_brawler)
            # opp1: Brawler = brawlers_map[opp_brawler](self.BRAWLERS, opp_brawler)
            opp1 = Shelly(self.BRAWLERS, "Shelly")

            # await ctx.send(embed=user1.brawler_info("Shelly", 10, 10, 5, 0, 200))

            user_health = user1._health(user_brawler_level)
            opp_health = opp1._health(opp_brawler_level)

            opp_health -= user1._attack(user_brawler_level)

            user_counter = 0
            opp_counter = 0

            winner = "Computer"
            margin = 0

            while True:
                # print(f"You before attack: {user_health}")
                # print(f"Computer before attack: {opp_health}")
                if user_counter > 0 and user_counter % 5 == 0:
                    res = user1._ult(user_brawler_level)
                    opp_health -= res
                    if res > 0:
                        user_counter += 1
                if opp_counter > 0 and opp_counter % 5 == 0:
                    res = opp1._ult(opp_brawler_level)
                    user_health -= res
                    if res > 0:
                        opp_counter += 1

                else:
                    res_u = user1._attack(user_brawler_level)
                    res_o = opp1._attack(opp_brawler_level)

                    if res_u > 0:
                        user_counter += 1
                    if res_o > 0:
                        opp_counter += 1

                    user_health -= res_o
                    opp_health -= res_u

                # print(f"You after attack: {user_health}")
                # print(f"Computer after attack: {opp_health}")

                margin = abs(user_health-opp_health)

                if user_health <= 0 and opp_health > 0:
                    break
                if opp_health <= 0 and user_health > 0:
                    winner = "User"
                    break
                if opp_health <= 0 and user_health <= 0:
                    winner = "Draw"
                    break
                else:
                    continue

            if winner == "Computer":
                results[player] = {
                    "brawl_res": -1,
                    "margin": margin
                }
            elif winner == "User":
                results[player] = {
                    "brawl_res": 1,
                    "margin": margin
                }
            else:
                results[player] = {
                    "brawl_res": 0,
                    "margin": margin
                }

        points = 0
        for result in results:
            if results[result]['brawl_res'] == 1:
                points += 1
            elif results[result]['brawl_res'] == -1:
                points -= 1
            else:
                points += 0

        starplayer = guild.me

        player_mentions = ' '.join([player.mention for player in players])
        
        if points > 0:
            # max_margin = 0
            # for result in results.keys():
            #     if results[result]['margin'] > max_margin:
            #         max_margin = results[result]['margin']
            #         starplayer = result
            #         if len(results) > 3:
            starplayer = random.choice([result for result in results])
            await ctx.send(f"{player_mentions} You won! Star Player: {starplayer}.")
        elif points < 1:
            await ctx.send(f"{player_mentions} You lost! Star Player: {starplayer}.")
        else:
            chance = random.randint(1, 2)
            if chance == 1:
                starplayer = random.choice([result for result in results])
            await ctx.send(f"The match ended in a draw! Star Player: {starplayer}.")

        count = 0
        for user in results:
            if user == starplayer:
                is_starplayer = True
            else:
                is_starplayer = False
            rewards = await self.brawl_rewards(user, points, is_starplayer)
            
            count += 1
            if count == 1:
                await ctx.send("Direct messaging rewards!")
            level_up = await self.xp_handler(user)
            try:
                await user.send(embed=rewards)
                if level_up:
                    await user.send(level_up[0])
                    await user.send(level_up[1])
            except:
                await ctx.send(f"Cannot direct message {user.mention}")
                await ctx.send(embed=rewards)
                if level_up:
                    await ctx.send(level_up[0])
                    await ctx.send(level_up[1])

    @commands.command(name="tutorial", aliases=["tut"])
    @commands.guild_only()
    # @commands.cooldown(rate=1, per=60, type=commands.BucketType.guild)
    async def _tutorial(self, ctx: Context):
        """Begin the tutorial."""

        author = ctx.author
        guild = ctx.guild
        author_avatar = author.avatar_url

        finished_tutorial = await self.get_player_stat(author, "tutorial_finished")

        # if finished_tutorial:
        #     return await ctx.send(
        #         "You have already finished the tutorial."
        #         " It's time to test your skills in the real world!"
        #     )

        desc = ("Hi, I'm Shelly! I'll introduce you to the world of BrawlCord."
                "Don't worry Brawler, it will only take a minute!")

        embed = discord.Embed(
            colour=0x9D4D4F, title="Tutorial", description=desc)
        # embed.set_author(name=author, icon_url=author_avatar)
        embed.set_thumbnail(url=imgur_links["shelly_tut"])

        useful_commands = (
            "`-brawl [teammate-1] [teammate-2]` Sends you on a Brawl!"
            "\n`-tutorial` Begins the tutorial!"
        )

        embed.add_field(name="Useful Commands", value=useful_commands)

        await ctx.send(embed=embed)

        await self.config.user(author).tutorial_finished.set(True)

    @commands.command(name="profile", aliases=["p", "pro"])
    async def _profile(self, ctx: Context, user: discord.User = None):
        """Display your or specified user's profile."""

        if not user:
            user = ctx.author
        
        embed = discord.Embed(colour=0xFFFFFF)
        embed.set_author(name=f"{user.name}'s Profile", icon_url=user.avatar_url)

        trophies = await self.get_trophies(user)
        embed.add_field(name="Trophies", value=f"{emojis['trophies']} {trophies:,}")

        pb = await self.get_trophies(user=user, pb=True)
        embed.add_field(name="Personal Best", value=f"{emojis['pb']} {pb:,}")

        xp = await self.get_player_stat(user, 'xp')
        lvl = await self.get_player_stat(user, 'lvl')
        next_xp = self.XP_LEVELS[str(lvl)]["Progress"]

        embed.add_field(name="Experience Level", value=f"{emojis['xp']} {lvl} `{xp}/{next_xp}`")

        gold = await self.get_player_stat(user, 'gold')
        embed.add_field(name="Gold", value=f"{emojis['gold']} {gold}")

        tokens = await self.get_player_stat(user, 'tokens')
        embed.add_field(name="Tokens", value=f"{emojis['token']} {tokens}")

        selected = await self.get_player_stat(user, 'selected', is_iter=True)
        brawler = selected['brawler']
        skin = selected['brawler_skin']
        gamemode = selected['gamemode']

        embed.add_field(name="Brawler", 
                value=f"{brawler_emojis[brawler]} {skin if skin != 'Default' else ''} {brawler}")
        embed.add_field(name="Game Mode", value=f"{gamemode_emotes[gamemode]} {gamemode}")

        await ctx.send(embed=embed)
    
    @commands.command(name="brawler", aliases=['binfo'])
    async def _brawler(self, ctx: Context, brawler_name: str, user: discord.User = None):
        """Get stats of a Brawler."""

        if not user:
            user = ctx.author
        
        brawlers = self.BRAWLERS

        # for users who input 'el-primo' or 'el_primo'
        brawler_name = brawler_name.replace("-", " ")
        brawler_name = brawler_name.replace("_", " ")

        brawler_name = brawler_name.title()

        for brawler in brawlers:
            if brawler_name in brawler:
                break
            else:
                brawler = None
        
        if not brawler:
            return await ctx.send(f"{brawler_name} does not exist.")
        
        owned_brawlers = await self.get_player_stat(user, 'brawlers', is_iter=True)

        owned = True if brawler in owned_brawlers else False

        b: Brawler = brawlers_map[brawler](self.BRAWLERS, brawler)

        if owned:
            brawler_data = await self.get_player_stat(user, 'brawlers', is_iter=True, substat=brawler)
            pp = brawler_data['powerpoints']
            next_level_pp = 20
            trophies = brawler_data['trophies']
            level = brawler_data['level']
            pb = brawler_data['pb']
            sp1 = brawler_data['sp1']
            sp2 = brawler_data['sp2']

            embed = b.brawler_info(brawler, trophies, pb, level, pp, next_level_pp, sp1, sp2)

        else:
            embed = b.brawler_info(brawler)

        await ctx.send(embed=embed)

    @commands.command(name="emojis")
    @checks.is_owner()
    async def get_all_emotes(self, ctx: Context):
        """Get all emojis of the server."""

        guild = ctx.guild

        server_emojis = await guild.fetch_emojis()

        print("brawler_emojis = {")
        for emoji in server_emojis:
            print(f"    \"{emoji.name}\": \"<:{emoji.name}:{emoji.id}>\",")
        print("}")
    
    async def get_player_stat(self, user: discord.User, stat: str, is_iter=False, substat: str = None):
        """Get stats of a player."""

        if not is_iter:
            return await getattr(self.config.user(user), stat)()

        async with getattr(self.config.user(user), stat)() as stat:
            if not substat:
                return stat
            else:
                return stat[substat]

    async def update_player_stat(self, user: discord.User, stat: str, 
                                                                    value, substat: str = None, sub_index=None):
        """Update stats of a player."""

        if substat:
            async with getattr(self.config.user(user), stat)() as stat:
                if not sub_index:
                    stat[substat] = value
                else:
                    stat[substat][sub_index] = value
        else:
            stat_attr = getattr(self.config.user(user), stat)
            await stat_attr.set(value)

    def matchmaking(self, brawler_level: int):
        """Get an opponent!"""

        opp_brawler = random.choice(list(self.BRAWLERS))

        opp_brawler_level = random.randint(brawler_level-1, brawler_level+1)
        opp_brawler_sp = None

        if opp_brawler_level > 10:
            opp_brawler_level = 10
            opp_brawler_sp = random.randint(1, 2)

        if opp_brawler_level < 1:
            opp_brawler_level = 1

        return opp_brawler, opp_brawler_level, opp_brawler_sp

    async def get_trophies(self, user: discord.User, pb = False, brawler_name: str = None):
        """Get total trophies or trophies of a specified Brawler of an user.

        Returns total trophies if a brawler is not specified.
        """

        brawlers = await self.get_player_stat(user, "brawlers")

        stat = "trophies" if not pb else "pb"

        if not brawler_name:
            return sum([brawlers[brawler][stat] for brawler in brawlers])
        else:
            return brawlers[brawler_name][stat]

    def buff_stats(self, brawler: Brawler, level: int):
        """Get Brawler stats by specified level."""

        # list of stats to buff
        stats_to_buff = [
            brawler.health,
            brawler.attack["damage"],
            brawler.ult["damage"]
        ]

    async def brawl_rewards(self, user: discord.User, points: int, is_starplayer=False):
        """Adjust user variables and return string containing reward."""

        if points > 0:
            reward_tokens = 20
            reward_xp = 8
            position = 1
        elif points < 0:
            reward_tokens = 10
            reward_xp = 4
            position = 2
        else:
            reward_tokens = 15
            reward_xp = 6
            position = 0

        if is_starplayer:
            reward_xp += 10

        tokens = await self.get_player_stat(user, 'tokens')
        tokens_in_bank = await self.get_player_stat(user, 'tokens_in_bank')

        if reward_tokens > tokens_in_bank:
            reward_tokens = tokens_in_bank

        tokens_in_bank -= reward_tokens

        # brawler trophies
        selected_brawler = await self.get_player_stat(user, 'selected', is_iter=True, substat='brawler')
        brawler_data = await self.get_player_stat(user, 'brawlers', is_iter=True, substat=selected_brawler)
        trophies = brawler_data['trophies']

        reward_trophies = self.trophies_to_reward_mapping(
            trophies, '3v3', position)

        xp = await self.get_player_stat(user, 'xp')
        xp += reward_xp

        tokens += reward_tokens
        trophies += reward_trophies

        await self.update_player_stat(user, 'tokens', tokens)
        await self.update_player_stat(user, 'tokens_in_bank', tokens_in_bank)
        await self.update_player_stat(user, 'xp', xp)
        await self.update_player_stat(user, 'brawlers', trophies,
                                      substat=selected_brawler, sub_index='trophies')
        await self.handle_pb(user, selected_brawler)

        user_avatar = user.avatar_url

        embed = discord.Embed(colour=0xFFFFFF, title="Rewards")
        embed.set_author(name=user.name, icon_url=user_avatar)

        reward_xp_str = f"{f'{reward_xp} (Star Player)' if is_starplayer else f'{reward_xp}'}"

        embed.add_field(name="Trophies", value=f"{emojis['trophies']} {reward_trophies}")
        embed.add_field(name="Tokens", value=f"{emojis['token']} {reward_tokens}")
        embed.add_field(name="Experience", value=f"{emojis['xp']} {reward_xp_str}")

        return embed

    def trophies_to_reward_mapping(self, trophies: int, game_type="3v3", position=1):

        # position correlates with the list index

        if trophies in range(0, 50):
            reward = self.REWARDS[game_type]["0-49"][position]
        elif trophies in range(50, 100):
            reward = self.REWARDS[game_type]["50-99"][position]
        elif trophies in range(100, 200):
            reward = self.REWARDS[game_type]["100-199"][position]
        elif trophies in range(200, 300):
            reward = self.REWARDS[game_type]["200-299"][position]
        elif trophies in range(300, 400):
            reward = self.REWARDS[game_type]["300-399"][position]
        elif trophies in range(400, 500):
            reward = self.REWARDS[game_type]["400-499"][position]
        elif trophies in range(500, 600):
            reward = self.REWARDS[game_type]["500-599"][position]
        elif trophies in range(600, 700):
            reward = self.REWARDS[game_type]["600-699"][position]
        elif trophies in range(700, 800):
            reward = self.REWARDS[game_type]["700-799"][position]
        elif trophies in range(800, 900):
            reward = self.REWARDS[game_type]["800-899"][position]
        elif trophies in range(900, 1000):
            reward = self.REWARDS[game_type]["900-999"][position]
        elif trophies in range(1000, 1100):
            reward = self.REWARDS[game_type]["1000-1099"][position]
        elif trophies in range(1100, 1200):
            reward = self.REWARDS[game_type]["1100-1199"][position]
        else:
            reward = self.REWARDS[game_type]["1200+"][position]

        return reward

    async def xp_handler(self, user: discord.User):
        """Handle xp level ups."""

        # xp = await self.config.user(ctx.author).xp()
        # lvl = await self.config.user(ctx.author).lvl()

        xp = await self.get_player_stat(user, 'xp')
        lvl = await self.get_player_stat(user, 'lvl')

        next_xp = self.XP_LEVELS[str(lvl)]["Progress"]

        if xp >= next_xp:
            carry = xp - next_xp
        else:
            return False

        await self.update_player_stat(user, 'xp', carry)
        await self.update_player_stat(user, 'lvl', lvl+1)

        level_up_msg = f"Level up! You have reached level {lvl+1}."

        tokens_reward = self.XP_LEVELS[str(lvl)]["TokensRewardCount"]
        reward_msg = f"Rewards: {tokens_reward} {emojis['token']}"

        tokens = await self.get_player_stat(user, 'tokens')
        tokens += tokens_reward
        await self.update_player_stat(user, 'tokens', tokens)

        return (level_up_msg, reward_msg)

    async def handle_pb(self, user: discord.User, brawler: str):
        """Handle personal best changes."""

        # individual brawler 
        trophies = await self.get_trophies(user=user, brawler_name=brawler)
        pb = await self.get_trophies(user=user, pb=True, brawler_name=brawler)

        if trophies > pb:
            await self.update_player_stat(user, 'brawlers', trophies, substat=brawler, sub_index='pb')
        
        # total trophies 
        # total_trophies = await self.get_trophies(user)
        # total_pb = await self.get_trophies(user=user, pb=True)

        # if total_trophies > total_pb:
        #     await self.up
