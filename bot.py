import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime

# CONFIGURAÇÕES - COLE OS IDs CORRETOS AQUI
CONFIG = {
    'aguardando_cargo_id': 1422448963625287761,
    'aprovado_cargo_id': 1421001020938522641,
    'canal_formulario_id': 1423057145875792003,
    'canal_aprovacao_id': 1423055315259363449,
    'log_channel_id': 1423051035575848963,
    'cargo_gerente_id': 1421001020955430985,
    'prefixo': '!'
}

# Dados para formulários e registros
formularios_ativos = {}
registro_membros = {}  # Para armazenar ID do jogo dos membros

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=CONFIG['prefixo'], intents=intents)

class IniciarFormularioView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Preencher Formulário", style=discord.ButtonStyle.primary, custom_id="iniciar_formulario")
    async def iniciar_formulario(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_roles = [role.id for role in interaction.user.roles]
        
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
        formularios_ativos[interaction.user.id] = {
            'respostas': [],
            'etapa': 0,
            'interaction': interaction
        }

        # Envia primeira pergunta via ephemeral
        await enviar_pergunta_formulario(interaction.user)

async def enviar_pergunta_formulario(usuario):
    if usuario.id not in formularios_ativos:
        return

    formulario = formularios_ativos[usuario.id]
    etapa = formulario['etapa']
    interaction = formulario['interaction']
    
    perguntas = [
        "🎮 **Qual seu Nome In-Game?**\n\n*Este será seu nickname no servidor*",
        "🆔 **Qual seu ID do Jogo?**\n\n*Digite apenas números*", 
        "👥 **Qual o ID do seu Recrutador?**\n\n*Digite apenas números*"
    ]
    
    if etapa >= len(perguntas):
        await finalizar_formulario(usuario)
        return

    try:
        # Envia a pergunta atual via ephemeral
        embed = discord.Embed(
            title=f"📋 FORMULÁRIO (Pergunta {etapa + 1}/3)",
            description=perguntas[etapa],
            color=0x0099ff
        )
        
        if etapa == 0:
            # Primeira pergunta - usa response.send_message
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Próximas perguntas - usa followup.send
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Aguarda resposta
        await aguardar_resposta_formulario(usuario, interaction.channel)
        
    except Exception as e:
        print(f"Erro ao enviar pergunta: {e}")
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]

async def aguardar_resposta_formulario(usuario, canal):
    if usuario.id not in formularios_ativos:
        return

    def check(m):
        # Verifica se a mensagem é do usuário no canal correto e não é comando
        is_correct_channel = m.channel.id == canal.id
        is_correct_user = m.author.id == usuario.id
        is_not_command = not m.content.startswith(CONFIG['prefixo'])
        has_content = len(m.content.strip()) > 0
        
        return is_correct_channel and is_correct_user and is_not_command and has_content

    try:
        # Aguarda resposta por 5 minutos
        resposta = await bot.wait_for('message', check=check, timeout=300)
        
        # Validações específicas por etapa
        formulario = formularios_ativos[usuario.id]
        etapa = formulario['etapa']
        
        if etapa == 1:  # Valida ID do Jogo (apenas números)
            if not resposta.content.strip().isdigit():
                await canal.send("❌ **ID do Jogo deve conter apenas números!** Tente novamente:", delete_after=10)
                return await aguardar_resposta_formulario(usuario, canal)
                
        elif etapa == 2:  # Valida ID do Recrutador (apenas números)
            if not resposta.content.strip().isdigit():
                await canal.send("❌ **ID do Recrutador deve conter apenas números!** Tente novamente:", delete_after=10)
                return await aguardar_resposta_formulario(usuario, canal)
        
        # Processa a resposta
        formulario['respostas'].append(resposta.content.strip())
        formulario['etapa'] += 1
        
        # Tenta deletar a resposta do usuário
        try:
            await resposta.delete()
        except:
            pass
        
        # Envia confirmação ephemeral
        interaction = formulario['interaction']
        if formulario['etapa'] < 3:
            confirmacao = f"✅ **Resposta {formulario['etapa']}/3 registrada!**"
            await interaction.followup.send(confirmacao, ephemeral=True)
            await enviar_pergunta_formulario(usuario)
        else:
            confirmacao = f"✅ **Resposta {formulario['etapa']}/3 registrada!**\n\nEnviando formulário..."
            await interaction.followup.send(confirmacao, ephemeral=True)
            await finalizar_formulario(usuario)
            
    except asyncio.TimeoutError:
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]
        try:
            interaction = formularios_ativos[usuario.id]['interaction']
            await interaction.followup.send("⏰ **Formulário expirado!** Você demorou muito para responder.", ephemeral=True)
        except:
            pass

async def finalizar_formulario(usuario):
    if usuario.id not in formularios_ativos:
        return

    formulario = formularios_ativos[usuario.id]
    
    if len(formulario['respostas']) != 3:
        try:
            interaction = formulario['interaction']
            await interaction.followup.send("❌ **Formulário incompleto!** Use o botão novamente para recomeçar.", ephemeral=True)
        except:
            pass
        del formularios_ativos[usuario.id]
        return

    try:
        # Confirmação para o usuário via ephemeral
        embed = discord.Embed(title="✅ FORMULÁRIO ENVIADO!", color=0x00ff00)
        embed.add_field(name="🎮 Nome In-Game", value=formulario['respostas'][0], inline=True)
        embed.add_field(name="🆔 ID do Jogo", value=formulario['respostas'][1], inline=True)
        embed.add_field(name="👥 ID Recrutador", value=formulario['respostas'][2], inline=True)
        embed.add_field(name="📊 Status", value="Aguardando aprovação da equipe...", inline=False)
        
        interaction = formulario['interaction']
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Envia para aprovação
        await enviar_para_aprovacao(usuario, formulario['respostas'])
        
        # Limpa formulário
        del formularios_ativos[usuario.id]

    except Exception as e:
        print(f"Erro ao finalizar formulário: {e}")
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]

async def enviar_para_aprovacao(usuario, respostas):
    canal_aprovacao = bot.get_channel(CONFIG['canal_aprovacao_id'])
    if canal_aprovacao:
        try:
            embed = discord.Embed(
                title="📋 NOVO FORMULÁRIO PARA APROVAÇÃO", 
                color=0xffff00, 
                timestamp=datetime.now()
            )
            embed.add_field(name="👤 USUÁRIO", value=f"{usuario.mention} ({usuario.name})", inline=False)
            embed.add_field(name="🎮 Nome In-Game", value=respostas[0], inline=True)
            embed.add_field(name="🆔 ID do Jogo", value=respostas[1], inline=True)
            embed.add_field(name="👥 ID Recrutador", value=respostas[2], inline=True)
            embed.add_field(name="🆔 ID Discord", value=usuario.id, inline=True)

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

            # Altera o nickname do usuário
            try:
                novo_nickname = f"{self.nome_in_game} | {self.id_jogo}"
                await usuario.edit(nick=novo_nickname)
                print(f"✅ Nickname alterado para: {novo_nickname}")
            except Exception as e:
                print(f"❌ Erro ao alterar nickname: {e}")

            # Registra o membro no sistema
            registro_membros[usuario.id] = {
                'nome_in_game': self.nome_in_game,
                'id_jogo': self.id_jogo,
                'id_recrutador': self.id_recrutador,
                'data_aprovacao': datetime.now()
            }

            # Atualiza a mensagem de aprovação
            embed = interaction.message.embeds[0]
            embed.color = 0x00ff00
            embed.add_field(name="✅ STATUS", value=f"Aprovado por {interaction.user.mention}", inline=False)
            embed.add_field(name="🔔 Ações realizadas", value=f"• Cargo atualizado\n• Nickname alterado: {novo_nickname}", inline=False)
            await interaction.message.edit(embed=embed, view=None)
            
            await interaction.response.send_message("✅ Usuário aprovado com sucesso!", ephemeral=True)

            # Envia mensagem para o usuário
            try:
                embed = discord.Embed(
                    title="🎉 PARABÉNS!",
                    description=f"Seu formulário foi **APROVADO**!\n\n**Nickname definido:** {novo_nickname}\n\nAgora você faz parte da nossa equipe!",
                    color=0x00ff00
                )
                await usuario.send(embed=embed)
            except:
                pass

            # Log no canal de logs
            await registrar_log(
                guild, 
                "✅ MEMBRO APROVADO", 
                f"{usuario.mention} foi aprovado\n**Nome In-Game:** {self.nome_in_game}\n**ID Jogo:** {self.id_jogo}",
                0x00ff00
            )

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
            # Remove todos os cargos
            await usuario.edit(roles=[])
            
            # Atualiza a mensagem
            embed = interaction.message.embeds[0]
            embed.color = 0xff0000
            embed.add_field(name="❌ STATUS", value=f"Reprovado por {interaction.user.mention}", inline=False)
            await interaction.message.edit(embed=embed, view=None)
            
            await interaction.response.send_message("❌ Usuário reprovado e removido!", ephemeral=True)
            
            # Envia mensagem antes de kickar
            try:
                embed = discord.Embed(
                    title="❌ FORMULÁRIO REPROVADO",
                    description="Seu formulário foi reprovado pela nossa equipe.\n\nVocê será removido do servidor.",
                    color=0xff0000
                )
                await usuario.send(embed=embed)
            except:
                pass
            
            # Log antes de kickar
            await registrar_log(
                guild, 
                "❌ MEMBRO REPROVADO", 
                f"{usuario.mention} foi reprovado\n**Nome In-Game:** {self.nome_in_game}\n**ID Jogo:** {self.id_jogo}",
                0xff0000
            )
            
            # Kicka o usuário
            await usuario.kick(reason="Formulário reprovado")

        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao reprovar: {e}", ephemeral=True)

async def registrar_log(guild, titulo, descricao, cor):
    """Registra log no canal de logs"""
    try:
        canal_logs = bot.get_channel(CONFIG['log_channel_id'])
        if canal_logs:
            embed = discord.Embed(
                title=titulo,
                description=descricao,
                color=cor,
                timestamp=datetime.now()
            )
            await canal_logs.send(embed=embed)
    except Exception as e:
        print(f"Erro ao registrar log: {e}")

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
                await registrar_log(
                    member.guild,
                    "👤 NOVO MEMBRO",
                    f"{member.mention} entrou no servidor\nCargo: {cargo_aguardando.name}",
                    0x00ff00
                )
            else:
                print(f"❌ Cargo Aguardando não encontrado (ID: {CONFIG['aguardando_cargo_id']})")
    except Exception as e:
        print(f"❌ Erro ao adicionar cargo para {member.name}: {e}")

@bot.event
async def on_member_remove(member):
    """Registra quando um membro sai do servidor"""
    print(f"Membro saiu: {member.name}")
    
    # Verifica se era um membro aprovado e registrado
    if member.id in registro_membros:
        dados = registro_membros[member.id]
        
        await registrar_log(
            member.guild,
            "🚪 MEMBRO SAIU",
            f"**{member.name}** saiu do servidor\n"
            f"**Nome In-Game:** {dados['nome_in_game']}\n"
            f"**ID Jogo:** {dados['id_jogo']}\n"
            f"**Recrutador:** {dados['id_recrutador']}\n"
            f"**Data de aprovação:** {dados['data_aprovacao'].strftime('%d/%m/%Y %H:%M')}",
            0xffa500  # Laranja
        )
        
        # Remove dos registros
        del registro_membros[member.id]
    else:
        # Membro não aprovado ou não registrado
        await registrar_log(
            member.guild,
            "🚪 MEMBRO SAIU",
            f"**{member.name}** saiu do servidor\n*(Não aprovado/registrado)*",
            0x808080  # Cinza
        )

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
    
    # Status dos registros
    embed.add_field(name="📈 Membros registrados", value=len(registro_membros), inline=True)
    embed.add_field(name="📝 Formulários ativos", value=len(formularios_ativos), inline=True)
    
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
                value="• Você deve ter o cargo 'Aguardando Formulário'\n• Preencha todas as informações corretamente\n• Aguarde a aprovação da equipe\n• **As perguntas aparecerão aqui (só você vê)**",
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
    embed.add_field(name="📈 Membros registrados", value=len(registro_membros), inline=True)
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
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN não encontrado nas variáveis de ambiente!")
    else:
        bot.run(token)
