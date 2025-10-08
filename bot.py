import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime

# Configurações
CONFIG = {
    'aguardando_cargo_id': None,
    'aprovado_cargo_id': None,
    'canal_formulario_id': None,
    'canal_aprovacao_id': None,
    'log_channel_id': None,
    'cargo_gerente_id': None,
    'prefixo': '!'
}

# Dados para relatório de recrutamento
recrutamento_data = {}
formularios_ativos = {}
nicknames_cache = {}
mensagem_botao_id = None

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=CONFIG['prefixo'], intents=intents)

class IniciarFormularioView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Preencher Formulário", style=discord.ButtonStyle.primary, custom_id="iniciar_formulario")
    async def iniciar_formulario(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not CONFIG['aguardando_cargo_id']:
            await interaction.response.send_message("❌ Sistema não configurado.", ephemeral=True)
            return

        user_roles = [role.id for role in interaction.user.roles]

        if CONFIG['aprovado_cargo_id'] and CONFIG['aprovado_cargo_id'] in user_roles:
            await interaction.response.send_message("✅ Você já foi aprovado!", ephemeral=True)
            return

        if CONFIG['aguardando_cargo_id'] not in user_roles:
            await interaction.response.send_message("❌ Você não está na lista de espera.", ephemeral=True)
            return

        if interaction.user.id in formularios_ativos:
            await interaction.response.send_message("❌ Formulário em andamento.", ephemeral=True)
            return

        await interaction.response.send_message("📋 **INICIANDO FORMULÁRIO...**", ephemeral=True)

        formularios_ativos[interaction.user.id] = {
            'respostas': [],
            'etapa': 1,
            'interaction': interaction
        }

        await enviar_pergunta_formulario(interaction.user, 1)

async def enviar_pergunta_formulario(usuario, etapa):
    if usuario.id not in formularios_ativos:
        return

    formulario = formularios_ativos[usuario.id]
    interaction = formulario['interaction']

    try:
        if etapa == 1:
            pergunta = "**Pergunta 1/3**\n\n🎮 **Qual seu Nome In-Game?**"
        elif etapa == 2:
            pergunta = "**Pergunta 2/3**\n\n🆔 **Qual seu ID do Jogo?**"
        elif etapa == 3:
            pergunta = "**Pergunta 3/3**\n\n👥 **Qual o ID do seu Recrutador?**"
        else:
            return

        embed = discord.Embed(title="📋 FORMULÁRIO", description=pergunta, color=0x0099ff)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await aguardar_resposta_formulario(usuario, interaction.channel)

    except Exception as e:
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]

async def aguardar_resposta_formulario(usuario, canal):
    if usuario.id not in formularios_ativos:
        return

    formulario = formularios_ativos[usuario.id]
    etapa_atual = formulario['etapa']

    try:
        resposta = await aguardar_resposta(usuario, canal, formulario)
        if not resposta:
            return

        formulario['respostas'].append(resposta)
        etapa_atual += 1
        formulario['etapa'] = etapa_atual

        if etapa_atual <= 3:
            await enviar_pergunta_formulario(usuario, etapa_atual)
        else:
            await finalizar_formulario(usuario, canal, formulario)

    except Exception as e:
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]

async def aguardar_resposta(usuario, canal, formulario, timeout=300):
    def check(m):
        return (m.author.id == usuario.id and m.channel.id == canal.id
                and not m.content.startswith(CONFIG['prefixo']))

    try:
        resposta = await bot.wait_for('message', check=check, timeout=timeout)
        try:
            await resposta.delete()
        except:
            pass
        return resposta.content

    except asyncio.TimeoutError:
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]
        return None

async def finalizar_formulario(usuario, canal, formulario):
    try:
        if len(formulario['respostas']) != 3:
            if usuario.id in formularios_ativos:
                del formularios_ativos[usuario.id]
            return

        embed = discord.Embed(title="✅ FORMULÁRIO ENVIADO!", color=0x00ff00)
        embed.add_field(name="🎮 Nome In-Game", value=formulario['respostas'][0], inline=True)
        embed.add_field(name="🆔 ID do Jogo", value=formulario['respostas'][1], inline=True)
        embed.add_field(name="👥 ID Recrutador", value=formulario['respostas'][2], inline=True)

        interaction = formulario['interaction']
        await interaction.followup.send(embed=embed, ephemeral=True)

        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]

        await enviar_para_aprovacao(usuario, formulario['respostas'])

    except Exception as e:
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]

async def enviar_para_aprovacao(usuario, respostas):
    if not CONFIG['canal_aprovacao_id']:
        return

    canal_aprovacao = bot.get_channel(CONFIG['canal_aprovacao_id'])
    if canal_aprovacao:
        try:
            embed = discord.Embed(title="📋 NOVO FORMULÁRIO", color=0xffff00, timestamp=datetime.now())
            embed.add_field(name="👤 USUÁRIO", value=f"{usuario.mention}", inline=False)
            embed.add_field(name="🎮 Nome In-Game", value=respostas[0], inline=True)
            embed.add_field(name="🆔 ID do Jogo", value=respostas[1], inline=True)
            embed.add_field(name="👥 ID Recrutador", value=respostas[2], inline=True)

            view = AprovacaoView(usuario.id, respostas[0], respostas[1], respostas[2])
            await canal_aprovacao.send(embed=embed, view=view)

        except Exception as e:
            print(f"Erro: {e}")

class AprovacaoView(discord.ui.View):
    def __init__(self, usuario_id, nome_in_game, id_jogo, id_recrutador):
        super().__init__(timeout=None)
        self.usuario_id = usuario_id
        self.nome_in_game = nome_in_game
        self.id_jogo = id_jogo
        self.id_recrutador = id_recrutador

    @discord.ui.button(label="✅ APROVAR", style=discord.ButtonStyle.success, custom_id="aprovar")
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if CONFIG['cargo_gerente_id'] and CONFIG['cargo_gerente_id'] not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas gerentes.", ephemeral=True)
            return

        guild = interaction.guild
        usuario = guild.get_member(self.usuario_id)

        if not usuario:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)
            return

        try:
            cargo_aguardando = guild.get_role(CONFIG['aguardando_cargo_id'])
            cargo_aprovado = guild.get_role(CONFIG['aprovado_cargo_id'])

            if cargo_aguardando and cargo_aguardando in usuario.roles:
                await usuario.remove_roles(cargo_aguardando)
            if cargo_aprovado:
                await usuario.add_roles(cargo_aprovado)

            embed = interaction.message.embeds[0]
            embed.color = 0x00ff00
            embed.add_field(name="✅ STATUS", value=f"Aprovado por {interaction.user.mention}", inline=False)
            await interaction.message.edit(embed=embed, view=None)
            await interaction.response.send_message("✅ Aprovado!", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    @discord.ui.button(label="❌ REPROVAR", style=discord.ButtonStyle.danger, custom_id="reprovar")
    async def reprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if CONFIG['cargo_gerente_id'] and CONFIG['cargo_gerente_id'] not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas gerentes.", ephemeral=True)
            return

        guild = interaction.guild
        usuario = guild.get_member(self.usuario_id)

        if not usuario:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)
            return

        try:
            await usuario.edit(roles=[])
            embed = interaction.message.embeds[0]
            embed.color = 0xff0000
            embed.add_field(name="❌ STATUS", value=f"Reprovado por {interaction.user.mention}", inline=False)
            await interaction.message.edit(embed=embed, view=None)
            await interaction.response.send_message("❌ Reprovado!", ephemeral=True)
            await usuario.kick(reason="Formulário reprovado")

        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} online!')
    bot.add_view(IniciarFormularioView())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Formulários | !ajuda"))

@bot.event
async def on_member_join(member):
    try:
        if CONFIG['aguardando_cargo_id']:
            cargo_aguardando = member.guild.get_role(CONFIG['aguardando_cargo_id'])
            if cargo_aguardando:
                await member.add_roles(cargo_aguardando)
    except:
        pass

@bot.command()
@commands.has_permissions(administrator=True)
async def configurar(ctx):
    await ctx.send("⚙️ Use `!criarbotao` após configurar os IDs manualmente no código.")

@bot.command()
@commands.has_permissions(administrator=True)
async def criarbotao(ctx):
    try:
        canal_formulario = bot.get_channel(CONFIG['canal_formulario_id'])
        if canal_formulario:
            embed = discord.Embed(title="📋 FORMULÁRIO", description="Clique para preencher.", color=0x0099ff)
            view = IniciarFormularioView()
            await canal_formulario.send(embed=embed, view=view)
            await ctx.send("✅ Botão criado!")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! {latency}ms')

@bot.command()
async def status(ctx):
    embed = discord.Embed(title="🤖 STATUS", color=0x00ff00)
    embed.add_field(name="📊 Servidores", value=len(bot.guilds), inline=True)
    embed.add_field(name="📋 Formulários ativos", value=len(formularios_ativos), inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def ajuda(ctx):
    embed = discord.Embed(title="📋 AJUDA", color=0x0099ff)
    embed.add_field(name="Comandos", value="!ping !status !ajuda", inline=False)
    await ctx.send(embed=embed)

if __name__ == "__main__":
    bot.run(os.environ['DISCORD_TOKEN'])
