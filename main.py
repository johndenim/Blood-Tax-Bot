# Blood-Tax-Bot
import discord
from discord import app_commands
import itertools
import os

intents = discord.Intents.default()

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

matches = {}

# =====================
# CHALLENGE UI
# =====================
class ChallengeView(discord.ui.View):
    def __init__(self, p1, p2, channel_id):
        super().__init__(timeout=None)
        self.p1 = p1
        self.p2 = p2
        self.channel_id = channel_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.p2:
            await interaction.response.send_message("Thou art not the one summoned to this duel.", ephemeral=True)
            return

        accepted_embed = discord.Embed(
            title="⚔️ BLOOD TAX CHALLENGE",
            description=(
                f"{self.p2.mention} hath accepted the challenge!\n\n"
                f"*Bring forth thy blood, curious one...*"
            ),
            color=0x8B0000
        )

        await interaction.response.edit_message(embed=accepted_embed, view=None)

        matches[self.channel_id] = {
            "p1": self.p1,
            "p2": self.p2,
            "channel_id": self.channel_id,
            "hp": {self.p1.id: 5, self.p2.id: 5},
            "deck": {
                self.p1.id: list(range(1, 11)),
                self.p2.id: list(range(1, 11))
            },
            "moves": {},
            "last_tax": None,
            "round": 1
        }

        channel = await client.fetch_channel(self.channel_id)
        await channel.send(
            f"⚔️ The blood pact is sealed! {self.p1.mention} faces {self.p2.mention} in the arena of taxation!"
        )

        await next_round(self.channel_id)

        self.stop()

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.p2:
            await interaction.response.send_message("Thou art not the one summoned to this duel.", ephemeral=True)
            return

        rejected_embed = discord.Embed(
            title="⚔️ BLOOD TAX CHALLENGE",
            description=(
                f"*Misfortune to thee who refuseth such an offer...*\n\n"
                f"{self.p2.mention} hath declined the challenge."
            ),
            color=0x2C2C2C
        )

        await interaction.response.edit_message(embed=rejected_embed, view=None)

        self.stop()

# =====================
# NUMBER SELECTION UI
# =====================
class NumberSelectView(discord.ui.View):
    def __init__(self, player, match):
        super().__init__(timeout=None)
        self.player = player
        self.match = match

        numbers = match["deck"][player.id]

        for n in numbers:
            self.add_item(NumberButton(n, player, match))


class NumberButton(discord.ui.Button):
    def __init__(self, number, player, match):
        super().__init__(label=str(number), style=discord.ButtonStyle.primary)
        self.number = number
        self.player = player
        self.match = match

    async def callback(self, interaction: discord.Interaction):

        if interaction.user != self.player:
            await interaction.response.send_message("This tribute is not thine to offer.", ephemeral=True)
            return

        if self.player.id in self.match["moves"]:
            await interaction.response.send_message("Thou hast already cast thy offering.", ephemeral=True)
            return

        self.match["moves"][self.player.id] = self.number

        await interaction.response.send_message(
            f"Thy offering of **{self.number}** hath been sealed in blood.", ephemeral=True
        )

        if len(self.match["moves"]) == 2:
            await resolve_round(self.match)


class ChooseView(discord.ui.View):
    def __init__(self, match):
        super().__init__(timeout=None)
        self.match = match

    @discord.ui.button(label="Offer thy Tribute", style=discord.ButtonStyle.success)
    async def choose(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id not in self.match["deck"]:
            await interaction.response.send_message("Thou art not bound to this blood tax.", ephemeral=True)
            return

        view = NumberSelectView(interaction.user, self.match)

        await interaction.response.send_message(
            "Choose thy offering wisely:", view=view, ephemeral=True
        )

# =====================
# CORE LOGIC
# =====================
def get_totals(p1, p2):
    return [a + b for a, b in itertools.product(p1, p2)]

def choose_tax_and_limit(p1, p2, last_tax):
    totals = get_totals(p1, p2)
    unique = sorted(set(totals))

    best_score = -999
    best = None

    for tax in unique:
        for window in range(1, 5):
            limit = tax + window

            unpaid = sum(1 for t in totals if t < tax)
            safe = sum(1 for t in totals if tax <= t <= limit)
            overflow = sum(1 for t in totals if t > limit)

            if unpaid == 0 or safe == 0 or overflow == 0:
                continue

            repeat_penalty = 3 if tax == last_tax else 0

            score = min(unpaid, safe, overflow) * 3 - abs(safe - 2) - repeat_penalty

            if score > best_score:
                best_score = score
                best = (tax, limit)

    if best is None:
        tax = min(unique)
        return tax, max(unique)

    return best

# =====================
# START COMMAND
# =====================
@tree.command(name="start", description="Challenge a player to Blood Tax")
async def start(interaction: discord.Interaction, opponent: discord.Member):
    try:
        await interaction.response.defer()

        p1 = interaction.user
        p2 = opponent

        if p1 == p2:
            await interaction.followup.send("Thou canst not challenge thyself, fool.", ephemeral=True)
            return

        if interaction.channel_id in matches:
            await interaction.followup.send(
                "A blood tax is already being collected in this chamber. Finish it first.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⚔️ BLOOD TAX CHALLENGE",
            description=(
                f"{p1.mention} hath issued a blood challenge to {p2.mention}!\n\n"
                f"*Dost thou accept this duel of taxation?*"
            ),
            color=0x8B0000
        )

        view = ChallengeView(p1, p2, interaction.channel_id)

        await interaction.followup.send(
            content=f"{p1.mention} vs {p2.mention}",
            embed=embed,
            view=view
        )
    except Exception as e:
        print(f"[ERROR] /start command failed: {e}", flush=True)

# =====================
# RULES COMMAND
# =====================
@tree.command(name="rules", description="Show how to play Blood Tax")
async def rules(interaction: discord.Interaction):
    await interaction.response.defer()

    embed = discord.Embed(
        title="🩸 BLOOD TAX — RULES",
        description=(
            "**🎮 Objective**\n"
            "Reduce your opponent to 0 HP or have more HP after 10 rounds.\n\n"

            "**📊 Setup**\n"
            "• Each player starts with 5 HP\n"
            "• Each player has numbers 1–10\n"
            "• Each number can only be used ONCE\n\n"

            "**🔁 Round Flow**\n"
            "1. Bot announces **Tax** and **Limit**\n"
            "2. Both players secretly choose a number\n"
            "3. Numbers are revealed and added\n\n"

            "**⚖️ Outcomes**\n"
            "• **PAID** → Total ≥ Tax AND ≤ Limit → No penalty\n"
            "• **UNPAID** → Total < Tax → Lower number loses 1 HP\n"
            "• **OVERFLOW** → Total > Limit → Higher number loses 1 HP\n\n"

            "**⚠️ Tie Rule**\n"
            "• If both players choose the SAME number in UNPAID or OVERFLOW → BOTH lose 1 HP\n\n"

            "**🏆 Winning**\n"
            "• Reduce opponent to 0 HP → Win\n"
            "• After 10 rounds → Higher HP wins\n"
            "• Equal HP → Draw\n"
        ),
        color=0x8B0000
    )

    await interaction.followup.send(embed=embed)

# =====================
# FORFEIT COMMAND
# =====================
@tree.command(name="forfeit", description="Forfeit the current match")
async def forfeit(interaction: discord.Interaction):
    await interaction.response.defer()

    channel_id = interaction.channel_id

    if channel_id not in matches:
        await interaction.followup.send("No blood tax is being collected in this chamber.", ephemeral=True)
        return

    match = matches[channel_id]
    user = interaction.user

    if user.id not in match["deck"]:
        await interaction.followup.send("Thou art not bound to this blood tax.", ephemeral=True)
        return

    p1 = match["p1"]
    p2 = match["p2"]

    winner = p2 if user == p1 else p1

    await interaction.followup.send(
        f"🏳️ {user.mention} hath surrendered their blood!\n🏆 {winner.mention} claims victory over the fallen!"
    )

    del matches[channel_id]

# =====================
# NEXT ROUND
# =====================
async def next_round(channel_id):
    match = matches[channel_id]

    p1 = match["p1"]
    p2 = match["p2"]

    p1_deck = match["deck"][p1.id]
    p2_deck = match["deck"][p2.id]

    if len(p1_deck) == 1 and len(p2_deck) == 1:
        tax = p1_deck[0] + p2_deck[0]
        limit = tax
    else:
        tax, limit = choose_tax_and_limit(p1_deck, p2_deck, match["last_tax"])

    match["tax"] = tax
    match["limit"] = limit
    match["last_tax"] = tax
    match["moves"] = {}

    channel = await client.fetch_channel(channel_id)

    view = ChooseView(match)

    await channel.send(
        f"💰 The Tax hath been decreed: **{tax}** | ⚠️ The Limit stands at: **{limit}**\n"
        f"⚔️ **ROUND {match['round']}** — Offer thy tribute!",
        view=view
    )

# =====================
# RESOLVE ROUND
# =====================
async def resolve_round(match):
    p1 = match["p1"]
    p2 = match["p2"]

    m1 = match["moves"][p1.id]
    m2 = match["moves"][p2.id]

    total = m1 + m2
    tax = match["tax"]
    limit = match["limit"]
    channel_id = match["channel_id"]

    if total < tax:
        verdict = "UNPAID"

        if m1 == m2:
            match["hp"][p1.id] -= 1
            match["hp"][p2.id] -= 1
            result = "Both souls bleed equally — 1 HP each"
        else:
            loser = p1 if m1 < m2 else p2
            match["hp"][loser.id] -= 1
            result = f"{loser.mention} bleeds — loses 1 HP"

    elif total > limit:
        verdict = "OVERFLOW"

        if m1 == m2:
            match["hp"][p1.id] -= 1
            match["hp"][p2.id] -= 1
            result = "Both souls bleed equally — 1 HP each"
        else:
            loser = p1 if m1 > m2 else p2
            match["hp"][loser.id] -= 1
            result = f"{loser.mention} bleeds — loses 1 HP"

    else:
        verdict = "PAID"
        result = "No blood is spilled this round"

    match["deck"][p1.id].remove(m1)
    match["deck"][p2.id].remove(m2)

    channel = await client.fetch_channel(channel_id)

    embed = discord.Embed(
        title=f"🩸 BLOOD TAX — ROUND {match['round']}",
        description=(
            f"**💰 Tax:** {tax}\n"
            f"**⚠️ Limit:** {limit}\n\n"
            f"**📥 Tributes Offered**\n"
            f"{p1.mention}: {m1}\n"
            f"{p2.mention}: {m2}\n"
            f"Total: {total}\n\n"
            f"**⚖️ The Verdict**\n"
            f"Status: {verdict}\n"
            f"Penalty: {result}\n\n"
            f"🩸 {p1.mention}: {match['hp'][p1.id]} HP\n"
            f"🩸 {p2.mention}: {match['hp'][p2.id]} HP"
        ),
        color=0x8B0000
    )

    await channel.send(embed=embed)

    # Check KO win
    if match["hp"][p1.id] <= 0 or match["hp"][p2.id] <= 0:
        if match["hp"][p1.id] > match["hp"][p2.id]:
            winner = p1
        elif match["hp"][p2.id] > match["hp"][p1.id]:
            winner = p2
        else:
            await channel.send("🤝 *The blood tax claims both equally... neither stands victorious. A draw!*")
            del matches[channel_id]
            return

        await channel.send(f"🏆 {winner.mention} hath vanquished their foe by knockout! The blood tax is satisfied.")
        del matches[channel_id]
        return

    # Check 10 rounds end
    if match["round"] >= 10:
        if match["hp"][p1.id] > match["hp"][p2.id]:
            winner = p1
            result_text = "hath endured more greatly — victory by blood remaining!"
        elif match["hp"][p2.id] > match["hp"][p1.id]:
            winner = p2
            result_text = "hath endured more greatly — victory by blood remaining!"
        else:
            await channel.send("🤝 *Ten rounds hath passed and neither soul prevails... The blood tax ends in a draw!*")
            del matches[channel_id]
            return

        await channel.send(f"🏆 {winner.mention} {result_text}")
        del matches[channel_id]
        return

    match["round"] += 1
    await next_round(channel_id)

# =====================
# READY EVENT
# =====================
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"[ERROR] Command '{interaction.command.name}' failed: {error}")
    try:
        await interaction.response.send_message("Something went wrong. The blood tax collector stumbled.", ephemeral=True)
    except Exception:
        pass

@client.event
async def on_ready():
    await tree.sync()
    print("Bot is ready!")

# =====================
# RUN BOT
# =====================
token = os.environ.get("DISCORD_TOKEN")
if not token:
    raise ValueError("DISCORD_TOKEN environment variable is not set.")

client.run(token)
