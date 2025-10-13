import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime, timedelta

# CONFIGURAÇÕES - COLE OS IDs CORRETOS AQUI
CONFIG = {
    'aguardando_cargo_id': 1422448963625287761,
    'aprovado_cargo_id': 1421001020938522641,
    'canal_formulario_id': 1423057145875792003,
    'canal_aprovacao_id': 1423055315259363449,
    'log_channel_id': 1423051035575848963,
    'cargo_gerente_id': 1421001020955430985,
    'canal_acoes_id': 1423057145875792003,  # Canal para ações (pode ser o mesmo do formulário)
    'prefixo': '!'
}

# Dados para formulários e registros
formularios_ativos = {}
registro_membros = {}
recrutamento_data = {}
acoes_ativas = {}  # Sistema de ações
hierarquia_roles = {  # Configuração das hierarquias
    '[L]': '🎯 Líder',
    '[CO]': '🛡️ Coordenador',
    '[GA]': '⚔️ Gerente de Ações', 
    '[SUB]': '🔰 Sub-Líder',
    '[MEM]': '👥 Membro'
}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=CONFIG['prefixo'], intents=intents)

# ========== SISTEMA DE FORMULÁRIO ==========
class IniciarFormularioView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Preencher Formulário", style=discord.ButtonStyle.primary, custom_id="iniciar_formulario")
    async def iniciar_formulario(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_roles = [role.id for role in interaction.user.roles]
        
        if CONFIG['aprovado_cargo_id'] in user_roles:
            await interaction.response.send_message("✅ Você já foi aprovado!", ephemeral=True)
            return

        if CONFIG['aguardando_cargo_id'] not in user_roles:
            await interaction.response.send_message("❌ Você não está na lista de espera.", ephemeral=True)
            return

        if interaction.user.id in formularios_ativos:
            await interaction.response.send_message("❌ Você já tem um formulário em andamento.", ephemeral=True)
            return

        formularios_ativos[interaction.user.id] = {
            'respostas': [],
            'etapa': 0,
            'interaction': interaction
        }

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
        embed = discord.Embed(
            title=f"📋 FORMULÁRIO (Pergunta {etapa + 1}/3)",
            description=perguntas[etapa],
            color=0x0099ff
        )
        
        if etapa == 0:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        await aguardar_resposta_formulario(usuario, interaction.channel)
        
    except Exception as e:
        print(f"Erro ao enviar pergunta: {e}")
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]

async def aguardar_resposta_formulario(usuario, canal):
    if usuario.id not in formularios_ativos:
        return

    def check(m):
        return (m.channel.id == canal.id and
                m.author.id == usuario.id and
                not m.content.startswith(CONFIG['prefixo']) and
                len(m.content.strip()) > 0)

    try:
        resposta = await bot.wait_for('message', check=check, timeout=300)
        
        formulario = formularios_ativos[usuario.id]
        etapa = formulario['etapa']
        
        if etapa == 1:
            if not resposta.content.strip().isdigit():
                await canal.send("❌ **ID do Jogo deve conter apenas números!** Tente novamente:", delete_after=10)
                return await aguardar_resposta_formulario(usuario, canal)
                
        elif etapa == 2:
            if not resposta.content.strip().isdigit():
                await canal.send("❌ **ID do Recrutador deve conter apenas números!** Tente novamente:", delete_after=10)
                return await aguardar_resposta_formulario(usuario, canal)
        
        formulario['respostas'].append(resposta.content.strip())
        formulario['etapa'] += 1
        
        try:
            await resposta.delete()
        except:
            pass
        
        interaction = formulario['interaction']
        if formulario['etapa'] < 3:
            await interaction.followup.send(f"✅ **Resposta {formulario['etapa']}/3 registrada!**", ephemeral=True)
            await enviar_pergunta_formulario(usuario)
        else:
            await interaction.followup.send(f"✅ **Resposta {formulario['etapa']}/3 registrada!**\n\nEnviando formulário...", ephemeral=True)
            await finalizar_formulario(usuario)
            
    except asyncio.TimeoutError:
        if usuario.id in formularios_ativos:
            del formularios_ativos[usuario.id]
        try:
            interaction = formularios_ativos[usuario.id]['interaction']
            await interaction.followup.send("⏰ **Formulário expirado!**", ephemeral=True)
        except:
            pass

async def finalizar_formulario(usuario):
    if usuario.id not in formularios_ativos:
        return

    formulario = formularios_ativos[usuario.id]
    
    if len(formulario['respostas']) != 3:
        try:
            interaction = formulario['interaction']
            await interaction.followup.send("❌ **Formulário incompleto!**", ephemeral=True)
        except:
            pass
        del formularios_ativos[usuario.id]
        return

    try:
        embed = discord.Embed(title="✅ FORMULÁRIO ENVIADO!", color=0x00ff00)
        embed.add_field(name="🎮 Nome In-Game", value=formulario['respostas'][0], inline=True)
        embed.add_field(name="🆔 ID do Jogo", value=formulario['respostas'][1], inline=True)
        embed.add_field(name="👥 ID Recrutador", value=formulario['respostas'][2], inline=True)
        embed.add_field(name="📊 Status", value="Aguardando aprovação...", inline=False)
        
        interaction = formulario['interaction']
        await interaction.followup.send(embed=embed, ephemeral=True)

        await enviar_para_aprovacao(usuario, formulario['respostas'])
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
        if CONFIG['cargo_gerente_id'] not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas gerentes podem aprovar.", ephemeral=True)
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

            try:
                novo_nickname = f"{self.nome_in_game} | {self.id_jogo}"
                await usuario.edit(nick=novo_nickname)
            except:
                pass

            data_aprovacao = datetime.now()
            registro_membros[usuario.id] = {
                'nome_in_game': self.nome_in_game,
                'id_jogo': self.id_jogo,
                'id_recrutador': self.id_recrutador,
                'data_aprovacao': data_aprovacao
            }

            if self.id_recrutador not in recrutamento_data:
                recrutamento_data[self.id_recrutador] = []
            
            recrutamento_data[self.id_recrutador].append({
                'id_jogo': self.id_jogo,
                'nome_in_game': self.nome_in_game,
                'data_recrutamento': data_aprovacao,
                'recrutador': self.id_recrutador
            })

            embed = interaction.message.embeds[0]
            embed.color = 0x00ff00
            embed.add_field(name="✅ STATUS", value=f"Aprovado por {interaction.user.mention}", inline=False)
            await interaction.message.edit(embed=embed, view=None)
            
            await interaction.response.send_message("✅ Usuário aprovado!", ephemeral=True)

            try:
                embed = discord.Embed(
                    title="🎉 PARABÉNS!",
                    description=f"Seu formulário foi **APROVADO**!\n\n**Nickname:** {novo_nickname}",
                    color=0x00ff00
                )
                await usuario.send(embed=embed)
            except:
                pass

            await registrar_log(guild, "✅ MEMBRO APROVADO", f"{usuario.mention} aprovado | Recrutador: {self.id_recrutador}", 0x00ff00)

        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

    @discord.ui.button(label="❌ REPROVAR", style=discord.ButtonStyle.danger, custom_id="reprovar")
    async def reprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if CONFIG['cargo_gerente_id'] not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas gerentes podem reprovar.", ephemeral=True)
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
            
            await interaction.response.send_message("❌ Usuário reprovado!", ephemeral=True)
            
            try:
                embed = discord.Embed(
                    title="❌ REPROVADO",
                    description="Seu formulário foi reprovado.",
                    color=0xff0000
                )
                await usuario.send(embed=embed)
            except:
                pass
            
            await registrar_log(guild, "❌ MEMBRO REPROVADO", f"{usuario.mention} reprovado", 0xff0000)
            await usuario.kick(reason="Reprovado")

        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

# ========== SISTEMA DE AÇÕES ==========
class ConfirmarAcaoView(discord.ui.View):
    def __init__(self, acao_id):
        super().__init__(timeout=None)
        self.acao_id = acao_id

    @discord.ui.button(label="✅ Participar", style=discord.ButtonStyle.success, custom_id="confirmar_acao")
    async def confirmar_participacao(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.acao_id not in acoes_ativas:
            await interaction.response.send_message("❌ Ação não encontrada.", ephemeral=True)
            return

        acao = acoes_ativas[self.acao_id]
        
        if interaction.user.id in acao['participantes']:
            await interaction.response.send_message("❌ Você já está participando!", ephemeral=True)
            return

        if len(acao['participantes']) >= acao['vagas']:
            await interaction.response.send_message("❌ Não há vagas!", ephemeral=True)
            return

        acao['participantes'][interaction.user.id] = {
            'nome': interaction.user.display_name,
            'adicionado_em': datetime.now()
        }

        await atualizar_mensagem_acao(acao)
        await interaction.response.send_message(f"✅ **Você entrou na ação!**\n{len(acao['participantes'])}/{acao['vagas']} vagas", ephemeral=True)

class AcaoView(discord.ui.View):
    def __init__(self, acao_id):
        super().__init__(timeout=None)
        self.acao_id = acao_id

    @discord.ui.button(label="👀 Ver Lista", style=discord.ButtonStyle.primary, custom_id="ver_participantes")
    async def ver_participantes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.acao_id not in acoes_ativas:
            await interaction.response.send_message("❌ Ação não encontrada.", ephemeral=True)
            return

        acao = acoes_ativas[self.acao_id]
        
        if not acao['participantes']:
            await interaction.response.send_message("📝 **Nenhum participante.**", ephemeral=True)
            return

        participantes_lista = "\n".join(f"• {p['nome']}" for p in acao['participantes'].values())

        embed = discord.Embed(
            title=f"👥 PARTICIPANTES - {acao['nome']}",
            description=participantes_lista,
            color=0x0099ff
        )
        embed.add_field(name="📊 Total", value=f"{len(acao['participantes'])}/{acao['vagas']}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="❌ Sair", style=discord.ButtonStyle.danger, custom_id="sair_acao")
    async def sair_acao(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.acao_id not in acoes_ativas:
            await interaction.response.send_message("❌ Ação não encontrada.", ephemeral=True)
            return

        acao = acoes_ativas[self.acao_id]
        
        if interaction.user.id not in acao['participantes']:
            await interaction.response.send_message("❌ Você não está nesta ação.", ephemeral=True)
            return

        participante = acao['participantes'][interaction.user.id]
        del acao['participantes'][interaction.user.id]

        await atualizar_mensagem_acao(acao)
        await interaction.response.send_message(f"✅ **Você saiu da ação!**", ephemeral=True)

async def atualizar_mensagem_acao(acao):
    try:
        canal = bot.get_channel(CONFIG['canal_acoes_id'])
        if canal and acao['mensagem_id']:
            mensagem = await canal.fetch_message(acao['mensagem_id'])
            
            embed = discord.Embed(
                title=f"⚔️ AÇÃO: {acao['nome']}",
                color=0xff0000 if len(acao['participantes']) >= acao['vagas'] else 0x00ff00
            )
            
            embed.add_field(name="📅 Data", value=acao['data'], inline=True)
            embed.add_field(name="🕐 Hora", value=acao['hora'], inline=True)
            embed.add_field(name="🎯 Vagas", value=f"{len(acao['participantes'])}/{acao['vagas']}", inline=True)
            
            if acao['participantes']:
                participantes_lista = "\n".join(f"• {p['nome']}" for p in list(acao['participantes'].values())[:8])
                if len(acao['participantes']) > 8:
                    participantes_lista += f"\n• ... e mais {len(acao['participantes']) - 8}"
            else:
                participantes_lista = "📝 Nenhum participante"
            
            embed.add_field(name="👥 Participantes", value=participantes_lista, inline=False)
            embed.set_footer(text=f"ID: {acao['id']}")

            view = AcaoView(acao['id'])
            await mensagem.edit(embed=embed, view=view)
            
    except Exception as e:
        print(f"Erro ao atualizar ação: {e}")

# ========== COMANDOS ==========
@bot.command()
@commands.has_permissions(administrator=True)
async def acao(ctx, vagas: int, data: str, hora: str, *, nome_acao: str):
    """Cria uma nova ação: !acao 10 15/12 20:30 Nome da Ação"""
    try:
        acao_id = f"acao_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        acoes_ativas[acao_id] = {
            'id': acao_id,
            'nome': nome_acao,
            'vagas': vagas,
            'data': data,
            'hora': hora,
            'participantes': {},
            'criador': ctx.author.id,
            'criado_em': datetime.now(),
            'mensagem_id': None
        }

        embed = discord.Embed(
            title=f"⚔️ NOVA AÇÃO: {nome_acao}",
            color=0x00ff00
        )
        
        embed.add_field(name="📅 Data", value=data, inline=True)
        embed.add_field(name="🕐 Hora", value=hora, inline=True)
        embed.add_field(name="🎯 Vagas", value=f"0/{vagas}", inline=True)
        embed.add_field(name="👥 Participantes", value="📝 Nenhum participante", inline=False)
        embed.add_field(name="📝 Como participar", value="Clique em '✅ Participar' abaixo", inline=False)
        embed.set_footer(text=f"ID: {acao_id}")

        view = ConfirmarAcaoView(acao_id)
        mensagem = await ctx.send(embed=embed, view=view)
        
        acoes_ativas[acao_id]['mensagem_id'] = mensagem.id
        await ctx.send(f"✅ **Ação criada!** ID: `{acao_id}`")

    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def fecharacao(ctx, acao_id: str):
    """Fecha uma ação: !fecharacao acao_20231215_203000"""
    if acao_id not in acoes_ativas:
        await ctx.send("❌ Ação não encontrada.")
        return

    acao = acoes_ativas[acao_id]
    
    embed = discord.Embed(
        title=f"📋 RELATÓRIO - {acao['nome']}",
        color=0xffa500
    )
    
    embed.add_field(name="📅 Data", value=acao['data'], inline=True)
    embed.add_field(name="🕐 Hora", value=acao['hora'], inline=True)
    embed.add_field(name="✅ Participantes", value=len(acao['participantes']), inline=True)
    embed.add_field(name="🎯 Vagas", value=f"{len(acao['participantes'])}/{acao['vagas']}", inline=True)

    if acao['participantes']:
        participantes_lista = "\n".join(f"• {p['nome']}" for p in acao['participantes'].values())
        embed.add_field(name="👥 Participantes", value=participantes_lista, inline=False)
    else:
        embed.add_field(name="👥 Participantes", value="❌ Nenhum", inline=False)

    await ctx.send(embed=embed)
    del acoes_ativas[acao_id]
    
    try:
        canal = bot.get_channel(CONFIG['canal_acoes_id'])
        if canal and acao['mensagem_id']:
            mensagem = await canal.fetch_message(acao['mensagem_id'])
            await mensagem.delete()
    except:
        pass

@bot.command()
async def hierarquia(ctx):
    """Mostra a hierarquia do servidor: !hierarquia"""
    try:
        guild = ctx.guild
        membros_hierarquia = {}
        
        for member in guild.members:
            if member.bot:
                continue
                
            nickname = member.display_name
            hierarquia_encontrada = None
            
            for tag, nome_hierarquia in hierarquia_roles.items():
                if tag in nickname:
                    hierarquia_encontrada = (tag, nome_hierarquia)
                    break
            
            if hierarquia_encontrada:
                tag, nome_hierarquia = hierarquia_encontrada
                if nome_hierarquia not in membros_hierarquia:
                    membros_hierarquia[nome_hierarquia] = []
                membros_hierarquia[nome_hierarquia].append(member)

        ordem_hierarquia = ['🎯 Líder', '🛡️ Coordenador', '⚔️ Gerente de Ações', '🔰 Sub-Líder', '👥 Membro']
        
        embed = discord.Embed(
            title="🏛️ HIERARQUIA DO SERVIDOR",
            description="Organização dos membros por cargos",
            color=0x2b2d31
        )

        for hierarquia in ordem_hierarquia:
            if hierarquia in membros_hierarquia:
                membros = membros_hierarquia[hierarquia]
                membros.sort(key=lambda x: x.display_name.lower())
                
                lista_membros = "\n".join(f"• {member.mention}" for member in membros[:10])
                
                if len(membros) > 10:
                    lista_membros += f"\n• ... e mais {len(membros) - 10}"
                
                embed.add_field(
                    name=f"{hierarquia} ({len(membros)})",
                    value=lista_membros if lista_membros.strip() else "Nenhum",
                    inline=False
                )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
async def acoesativas(ctx):
    """Mostra ações ativas: !acoesativas"""
    if not acoes_ativas:
        await ctx.send("📝 **Nenhuma ação ativa.**")
        return

    embed = discord.Embed(title="📋 AÇÕES ATIVAS", color=0x0099ff)

    for acao_id, acao in acoes_ativas.items():
        embed.add_field(
            name=f"⚔️ {acao['nome']}",
            value=f"**Data:** {acao['data']} | **Hora:** {acao['hora']}\n**Vagas:** {len(acao['participantes'])}/{acao['vagas']}\n**ID:** `{acao_id}`",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def removerparticipante(ctx, acao_id: str, member: discord.Member):
    """Remove participante: !removerparticipante acao_123 @user"""
    if acao_id not in acoes_ativas:
        await ctx.send("❌ Ação não encontrada.")
        return

    acao = acoes_ativas[acao_id]
    
    if member.id not in acao['participantes']:
        await ctx.send("❌ Usuário não está na ação.")
        return

    participante = acao['participantes'][member.id]
    del acao['participantes'][member.id]

    await atualizar_mensagem_acao(acao)
    await ctx.send(f"✅ **{member.display_name} removido da ação!**")

# ========== COMANDOS EXISTENTES ==========
@bot.command()
@commands.has_permissions(administrator=True)
async def relatorio(ctx, periodo: str = "mensal"):
    """Relatório de recrutamento: !relatorio [mensal|30d|7d|total]"""
    try:
        agora = datetime.now()
        
        if periodo.lower() == "mensal":
            primeiro_dia = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            titulo = "📊 RELATÓRIO MENSAL"
            periodo_str = primeiro_dia.strftime('%B/%Y')
        elif periodo.lower() == "30d":
            primeiro_dia = agora - timedelta(days=30)
            titulo = "📊 RELATÓRIO - 30 DIAS"
            periodo_str = f"Últimos 30 dias"
        elif periodo.lower() == "7d":
            primeiro_dia = agora - timedelta(days=7)
            titulo = "📊 RELATÓRIO - 7 DIAS"
            periodo_str = f"Últimos 7 dias"
        elif periodo.lower() == "total":
            primeiro_dia = datetime.min
            titulo = "📊 RELATÓRIO TOTAL"
            periodo_str = "Todos os tempos"
        else:
            await ctx.send("❌ Use: mensal, 30d, 7d ou total")
            return

        recrutadores_filtrados = {}
        for recrutador_id, recrutamentos in recrutamento_data.items():
            recrutamentos_filtrados = [r for r in recrutamentos if r['data_recrutamento'] >= primeiro_dia]
            if recrutamentos_filtrados:
                recrutadores_filtrados[recrutador_id] = recrutamentos_filtrados

        if not recrutadores_filtrados:
            embed = discord.Embed(title=titulo, description=f"**Período:** {periodo_str}\nNenhum dado.", color=0x808080)
            await ctx.send(embed=embed)
            return

        recrutadores_ordenados = sorted(recrutadores_filtrados.items(), key=lambda x: len(x[1]), reverse=True)

        embed = discord.Embed(title=titulo, description=f"**Período:** {periodo_str}", color=0x0099ff)

        for i, (recrutador_id, recrutamentos) in enumerate(recrutadores_ordenados[:10], 1):
            embed.add_field(
                name=f"#{i} - ID: {recrutador_id}",
                value=f"**Recrutamentos:** {len(recrutamentos)}",
                inline=True
            )

        total_recrutamentos = sum(len(r) for r in recrutadores_filtrados.values())
        embed.add_field(name="📈 ESTATÍSTICAS", value=f"**Total:** {total_recrutamentos}\n**Recrutadores:** {len(recrutadores_filtrados)}", inline=False)

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def criarbotao(ctx):
    """Cria botão do formulário: !criarbotao"""
    try:
        canal = bot.get_channel(CONFIG['canal_formulario_id'])
        if canal:
            embed = discord.Embed(
                title="📋 FORMULÁRIO DE RECRUTAMENTO",
                description="Clique para preencher o formulário.",
                color=0x0099ff
            )
            view = IniciarFormularioView()
            await canal.send(embed=embed, view=view)
            await ctx.send("✅ Botão criado!")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
async def ping(ctx):
    """Testa latência: !ping"""
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! {latency}ms')

@bot.command()
async def status(ctx):
    """Status do bot: !status"""
    embed = discord.Embed(title="🤖 STATUS", color=0x00ff00)
    embed.add_field(name="📊 Servidores", value=len(bot.guilds), inline=True)
    embed.add_field(name="👤 Usuários", value=len(bot.users), inline=True)
    embed.add_field(name="📋 Formulários", value=len(formularios_ativos), inline=True)
    embed.add_field(name="📈 Membros", value=len(registro_membros), inline=True)
    embed.add_field(name="⚔️ Ações", value=len(acoes_ativas), inline=True)
    embed.add_field(name="🏓 Latência", value=f"{round(bot.latency * 1000)}ms", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def ajuda(ctx):
    """Ajuda: !ajuda"""
    embed = discord.Embed(title="📋 AJUDA", color=0x0099ff)
    
    embed.add_field(
        name="👤 Comandos Públicos",
        value="`!ping` `!status` `!ajuda` `!hierarquia` `!acoesativas`",
        inline=False
    )
    
    embed.add_field(
        name="⚔️ Sistema de Ações", 
        value="`!acao 10 15/12 20:30 Nome`\n`!fecharacao ID`\n`!acoesativas`",
        inline=False
    )
    
    embed.add_field(
        name="📊 Relatórios",
        value="`!relatorio [mensal|30d|7d|total]`",
        inline=False
    )
    
    embed.add_field(
        name="👑 Administrador",
        value="`!criarbotao` `!removerparticipante ID @user`",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ========== EVENTOS ==========
@bot.event
async def on_ready():
    print(f'✅ {bot.user.name} online!')
    bot.add_view(IniciarFormularioView())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="!ajuda"))

@bot.event
async def on_member_join(member):
    try:
        if CONFIG['aguardando_cargo_id']:
            cargo = member.guild.get_role(CONFIG['aguardando_cargo_id'])
            if cargo:
                await member.add_roles(cargo)
                await registrar_log(member.guild, "👤 NOVO MEMBRO", f"{member.mention} entrou", 0x00ff00)
    except Exception as e:
        print(f"Erro: {e}")

@bot.event
async def on_member_remove(member):
    if member.id in registro_membros:
        dados = registro_membros[member.id]
        await registrar_log(member.guild, "🚪 MEMBRO SAIU", f"**{member.name}** saiu\nRecrutador: {dados['id_recrutador']}", 0xffa500)
        del registro_membros[member.id]

async def registrar_log(guild, titulo, descricao, cor):
    try:
        canal = bot.get_channel(CONFIG['log_channel_id'])
        if canal:
            embed = discord.Embed(title=titulo, description=descricao, color=cor, timestamp=datetime.now())
            await canal.send(embed=embed)
    except:
        pass

if __name__ == "__main__":
    token = os.environ.get('DISCORD_TOKEN')
    if token:
        bot.run(token)
    else:
        print("❌ Token não encontrado!")
