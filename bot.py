import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime

# CONFIGURAÇÕES - COLE OS IDs CORRETOS AQUI
CONFIG = {
    'aguardando_cargo_id': 1422448963625287761,  # ID do cargo "Aguardando Formulário"
    'aprovado_cargo_id': 1421001020938522641,    # ID do cargo "Aprovado"
    'canal_formulario_id': 1423057145875792003,  # ID do canal do formulário
    'canal_aprovacao_id': 1423055315259363449,   # ID do canal de aprovação
    'log_channel_id': 1423051035575848963,       # ID do canal de logs
    'cargo_gerente_id': 1421001020955430985,     # ID do cargo de gerente
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
        # Verifica se o usuário tem o cargo de aguardando
        user_roles = [role.id for role in interaction.user.roles]
        
        print(f"Usuário {interaction.user.name} clicou no botão")
        print(f"Cargos do usuário: {user_roles}")
        print(f"Cargo aguardando: {CONFIG['aguardando_cargo_id']}")

        # Verifica se já foi aprovado
        if CONFIG['aprovado_cargo_id'] in user_roles:
            await interaction.response.send_message("✅ Você já foi aprovado!", ephemeral=True)
            return

        # Verifica se está na lista de espera
        if CONFIG['aguardando_cargo_id'] not in user_roles:
            await interaction.response.send_message(
                "❌ Você não está na lista de espera.\n\n"
                "⚠️ **Soluções possíveis:**\n"
                "• Aguarde alguns segundos e tente novamente\n"
                "• Entre no servidor novamente\n"
                "• Contate um administrador", 
                ephemeral=True
            )
            return

        # Verifica se já tem formulário ativo
        if interaction.user.id in formularios_ativos:
            await interaction.response.send_message("❌ Você já tem um formulário em andamento.", ephemeral=True)
            return

        # Inicia o formulário
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

    except Exception as e:
        print(f"Erro ao enviar pergunta: {e}")
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]

async def aguardar_resposta_formulario(usuario, canal):
    if usuario.id not in formularios_ativos:
        return

    formulario = formularios_ativos[usuario.id]
    etapa_atual = formulario['etapa']

    def check(m):
        return m.author.id == usuario.id and m.channel.id == canal.id

    try:
        resposta = await bot.wait_for('message', check=check, timeout=300)
        
        # Tenta deletar a mensagem da resposta
        try:
            await resposta.delete()
        except:
            pass

        formulario['respostas'].append(resposta.content)
        etapa_atual += 1
        formulario['etapa'] = etapa_atual

        if etapa_atual <= 3:
            await enviar_pergunta_formulario(usuario, etapa_atual)
            await aguardar_resposta_formulario(usuario, canal)
        else:
            await finalizar_formulario(usuario, canal, formulario)

    except asyncio.TimeoutError:
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]
        await canal.send("⏰ Formulário expirado. Use o botão novamente.", delete_after=10)

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
        print(f"Erro ao finalizar formulário: {e}")
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]

async def enviar_para_aprovacao(usuario, respostas):
    canal_aprovacao = bot.get_channel(CONFIG['canal_aprovacao_id'])
    if canal_aprovacao:
        try:
            embed = discord.Embed(title="📋 NOVO FORMULÁRIO", color=0xffff00, timestamp=datetime.now())
            embed.add_field(name="👤 USUÁRIO", value=f"{usuario.mention} ({usuario.name})", inline=False)
            embed.add_field(name="🎮 Nome In-Game", value=respostas[0], inline=True)
            embed.add_field(name="🆔 ID do Jogo", value=respostas[1], inline=True)
            embed.add_field(name="👥 ID Recrutador", value=respostas[2], inline=True)

            view = AprovacaoView(usuario.id, respostas[0], respostas[1], respostas[2])
            await canal_aprovacao.send(embed=embed, view=view)

        except Exception as e:
            print(f"Erro ao enviar para aprovação: {e}")

class AprovacaoView(discord.ui.View):
    def __init__(self, usuario_id, nome_in_game, id_jogo, id_recrutador):
        super().__init__(timeout=None)
        self.usuario_id = usuario_id
        self.nome_in_game = nome_in_game
        self.id_jogo = id_jogo
        self.id_recrutador = id_recrutador

    @discord.ui.button(label="✅ APROVAR", style=discord.ButtonStyle.success, custom_id="aprovar")
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verifica permissão
        if CONFIG['cargo_gerente_id'] not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas gerentes podem aprovar.", ephemeral=True)
            return

        guild = interaction.guild
        usuario = guild.get_member(self.usuario_id)

        if not usuario:
            await interaction.response.send_message("❌ Usuário não encontrado no servidor.", ephemeral=True)
            return

        try:
            # Remove cargo de aguardando e adiciona aprovado
            cargo_aguardando = guild.get_role(CONFIG['aguardando_cargo_id'])
            cargo_aprovado = guild.get_role(CONFIG['aprovado_cargo_id'])
            
            if cargo_aguardando and cargo_aguardando in usuario.roles:
                await usuario.remove_roles(cargo_aguardando)
            if cargo_aprovado:
                await usuario.add_roles(cargo_aprovado)

            # Atualiza a mensagem
            embed = interaction.message.embeds[0]
            embed.color = 0x00ff00
            embed.add_field(name="✅ STATUS", value=f"Aprovado por {interaction.user.mention}", inline=False)
            await interaction.message.edit(embed=embed, view=None)
            
            await interaction.response.send_message("✅ Usuário aprovado com sucesso!", ephemeral=True)

            # Envia mensagem para o usuário
            try:
                await usuario.send("🎉 **Parabéns! Seu formulário foi aprovado!**\n\nAgora você faz parte da nossa equipe!")
            except:
                pass

        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao aprovar: {e}", ephemeral=True)

    @discord.ui.button(label="❌ REPROVAR", style=discord.ButtonStyle.danger, custom_id="reprovar")
    async def reprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if CONFIG['cargo_gerente_id'] not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas gerentes podem reprovar.", ephemeral=True)
            return

        guild = interaction.guild
        usuario = guild.get_member(self.usuario_id)

        if not usuario:
            await interaction.response.send_message("❌ Usuário não encontrado no servidor.", ephemeral=True)
            return

        try:
            # Remove todos os cargos e kicka
            await usuario.edit(roles=[])
            
            # Atualiza a mensagem
            embed = interaction.message.embeds[0]
            embed.color = 0xff0000
            embed.add_field(name="❌ STATUS", value=f"Reprovado por {interaction.user.mention}", inline=False)
            await interaction.message.edit(embed=embed, view=None)
            
            await interaction.response.send_message("❌ Usuário reprovado e removido!", ephemeral=True)
            
            # Kicka o usuário
            await usuario.kick(reason="Formulário reprovado")

        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao reprovar: {e}", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ {bot.user.name} online!')
    print(f'📊 Conectado em {len(bot.guilds)} servidor(es)')
    
    # Adiciona a view persistente
    bot.add_view(IniciarFormularioView())
    
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Formulários | !ajuda"))

@bot.event
async def on_member_join(member):
    print(f"Novo membro: {member.name} entrou no servidor")
    
    try:
        if CONFIG['aguardando_cargo_id']:
            cargo_aguardando = member.guild.get_role(CONFIG['aguardando_cargo_id'])
            if cargo_aguardando:
                await member.add_roles(cargo_aguardando)
                print(f"Cargo 'Aguardando' adicionado para {member.name}")
                
                # Log no canal de logs
                canal_logs = bot.get_channel(CONFIG['log_channel_id'])
                if canal_logs:
                    embed = discord.Embed(
                        title="👤 NOVO MEMBRO",
                        description=f"{member.mention} entrou no servidor",
                        color=0x00ff00,
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Cargo adicionado", value=cargo_aguardando.name, inline=True)
                    await canal_logs.send(embed=embed)
            else:
                print(f"❌ Cargo Aguardando não encontrado (ID: {CONFIG['aguardando_cargo_id']})")
    except Exception as e:
        print(f"❌ Erro ao adicionar cargo para {member.name}: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def verificar_config(ctx):
    """Verifica a configuração atual do bot"""
    embed = discord.Embed(title="⚙️ CONFIGURAÇÃO ATUAL", color=0x0099ff)
    
    # Verifica cargos
    cargo_aguardando = ctx.guild.get_role(CONFIG['aguardando_cargo_id'])
    cargo_aprovado = ctx.guild.get_role(CONFIG['aprovado_cargo_id'])
    cargo_gerente = ctx.guild.get_role(CONFIG['cargo_gerente_id'])
    
    embed.add_field(name="🔄 Cargo Aguardando", value=f"{cargo_aguardando.mention if cargo_aguardando else '❌ Não encontrado'}", inline=True)
    embed.add_field(name="✅ Cargo Aprovado", value=f"{cargo_aprovado.mention if cargo_aprovado else '❌ Não encontrado'}", inline=True)
    embed.add_field(name="👑 Cargo Gerente", value=f"{cargo_gerente.mention if cargo_gerente else '❌ Não encontrado'}", inline=True)
    
    # Verifica canais
    canal_form = bot.get_channel(CONFIG['canal_formulario_id'])
    canal_aprov = bot.get_channel(CONFIG['canal_aprovacao_id'])
    canal_logs = bot.get_channel(CONFIG['log_channel_id'])
    
    embed.add_field(name="📋 Canal Formulário", value=f"{canal_form.mention if canal_form else '❌ Não encontrado'}", inline=True)
    embed.add_field(name="📝 Canal Aprovação", value=f"{canal_aprov.mention if canal_aprov else '❌ Não encontrado'}", inline=True)
    embed.add_field(name="📊 Canal Logs", value=f"{canal_logs.mention if canal_logs else '❌ Não encontrado'}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def criarbotao(ctx):
    """Cria o botão do formulário no canal configurado"""
    try:
        canal_formulario = bot.get_channel(CONFIG['canal_formulario_id'])
        if canal_formulario:
            embed = discord.Embed(
                title="📋 FORMULÁRIO DE RECRUTAMENTO",
                description="Clique no botão abaixo para preencher o formulário de recrutamento.",
                color=0x0099ff
            )
            embed.add_field(
                name="ℹ️ INSTRUÇÕES",
                value="• Você deve ter o cargo 'Aguardando Formulário'\n• Preencha todas as informações corretamente\n• Aguarde a aprovação da equipe",
                inline=False
            )
            
            view = IniciarFormularioView()
            await canal_formulario.send(embed=embed, view=view)
            await ctx.send("✅ Botão do formulário criado com sucesso!")
        else:
            await ctx.send("❌ Canal de formulário não encontrado!")
    except Exception as e:
        await ctx.send(f"❌ Erro ao criar botão: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def addcargo(ctx, member: discord.Member):
    """Adiciona manualmente o cargo de aguardando a um membro"""
    try:
        cargo_aguardando = ctx.guild.get_role(CONFIG['aguardando_cargo_id'])
        if cargo_aguardando:
            await member.add_roles(cargo_aguardando)
            await ctx.send(f"✅ Cargo adicionado para {member.mention}")
        else:
            await ctx.send("❌ Cargo 'Aguardando' não encontrado")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
async def ping(ctx):
    """Mostra a latência do bot"""
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! {latency}ms')

@bot.command()
async def status(ctx):
    """Mostra o status do bot"""
    embed = discord.Embed(title="🤖 STATUS DO BOT", color=0x00ff00)
    embed.add_field(name="📊 Servidores", value=len(bot.guilds), inline=True)
    embed.add_field(name="👤 Usuários", value=len(bot.users), inline=True)
    embed.add_field(name="📋 Formulários ativos", value=len(formularios_ativos), inline=True)
    embed.add_field(name="🏓 Latência", value=f"{round(bot.latency * 1000)}ms", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def ajuda(ctx):
    """Mostra os comandos disponíveis"""
    embed = discord.Embed(title="📋 AJUDA - COMANDOS DISPONÍVEIS", color=0x0099ff)
    
    embed.add_field(
        name="👤 Comandos Públicos",
        value="`!ping` - Verifica a latência\n`!status` - Status do bot\n`!ajuda` - Esta mensagem",
        inline=False
    )
    
    embed.add_field(
        name="👑 Comandos de Administrador",
        value="`!verificar_config` - Verifica configuração\n`!criarbotao` - Cria botão do formulário\n`!addcargo @usuário` - Adiciona cargo manualmente",
        inline=False
    )
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    # Verifica se o token está configurado
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN não encontrado nas variáveis de ambiente!")
    else:
        bot.run(token)
