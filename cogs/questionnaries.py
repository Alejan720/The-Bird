import json
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from database import Database

class CuestionarioModal(discord.ui.Modal, title="Crear Cuestionario Avanzado"):
    titulo = discord.ui.TextInput(
        label="Título del Cuestionario",
        placeholder="Ej: Elige tus Roles / Asignaturas...",
        style=discord.TextStyle.short,
        required=True
    )
    
    pregunta = discord.ui.TextInput(
        label="Pregunta",
        placeholder="¿Qué opciones deseas seleccionar?",
        style=discord.TextStyle.paragraph,
        required=True
    )
    
    opciones = discord.ui.TextInput(
        label="Opciones (separadas por comas - Creamos roles)",
        placeholder="Opción 1, Opción 2, Opción 3",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=400
    )

    multiple_seleccion = discord.ui.TextInput(
        label="¿Permitir elegir varias opciones? (Sí/No)",
        placeholder="Escribe 'Sí' si se pueden marcar varias, o 'No' para única",
        style=discord.TextStyle.short,
        required=True,
        max_length=3
    )

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    async def on_submit(self, interaction: discord.Interaction):
        lista_opciones = [op.strip() for op in self.opciones.value.split(",") if op.strip()]

        if interaction.guild is None:
            await interaction.response.send_message("Este cuestionario solo se puede crear en un servidor.", ephemeral=True)
            return

        if len({op.casefold() for op in lista_opciones}) != len(lista_opciones):
            await interaction.response.send_message("No repitas opciones; cada una debe ser única.", ephemeral=True)
            return
        
        if len(lista_opciones) < 2 or len(lista_opciones) > 5:
            await interaction.response.send_message("❌ Debes introducir entre **2 y 5 opciones** válidas separadas por comas.", ephemeral=True)
            return

        is_multiple = self.multiple_seleccion.value.strip().lower() in ["sí", "si", "yes", "s"]

        # No reutilizar roles preexistentes: una opción nunca debe conceder permisos sensibles.
        roles_creados_ids = []
        for op in lista_opciones:
            try:
                nuevo_rol = await interaction.guild.create_role(
                    name=op[:100], reason=f"Cuestionario creado por {interaction.user}"
                )
                roles_creados_ids.append(nuevo_rol.id)
            except discord.HTTPException:
                roles_creados_ids.append(None)

        # Construir la vista interactiva
        questionnaire_id = await self.db.create_questionnaire(
            interaction.guild.id,
            interaction.user.id,
            interaction.channel_id,
            self.titulo.value,
            self.pregunta.value,
            json.dumps(lista_opciones, ensure_ascii=False),
            json.dumps({"roles": roles_creados_ids, "multiple": is_multiple}),
            datetime.now(timezone.utc).isoformat(),
        )
        view = CuestionarioView(questionnaire_id, self.db, lista_opciones, roles_creados_ids, is_multiple)

        embed = discord.Embed(
            title=f"📋 {self.titulo.value}",
            description=f"**{self.pregunta.value}**\n\n*(Modo: {'**Múltiples respuestas permitidas**' if is_multiple else '**Respuesta única**'})\n(¡Al pulsar se crearán/asignarán los roles correspondientes!)*",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        letras = ["🇦", "🇧", "🇨", "🇩", "🇪"]
        opciones_formato = "\n".join([f"{letras[i]} {op}" for i, op in enumerate(lista_opciones)])
        embed.add_field(name="Opciones Disponibles", value=opciones_formato, inline=False)
        embed.set_footer(text=f"Creado por {interaction.user.display_name}")

        try:
            mensaje_publico = await interaction.channel.send(embed=embed, view=view)
        except discord.HTTPException:
            await self.db.deactivate_questionnaire(questionnaire_id)
            await interaction.response.send_message(
                "No pude publicar el cuestionario. Revisa los permisos del bot en este canal.", ephemeral=True
            )
            return
        view.message = mensaje_publico
        await self.db.set_questionnaire_message(questionnaire_id, mensaje_publico.id)
        await interaction.response.send_message("✅ ¡Cuestionario creado con éxito!", ephemeral=True)


class CuestionarioView(discord.ui.View):
    def __init__(self, questionnaire_id: int, db: Database, opciones: list, roles_ids: list, multiple: bool):
        super().__init__(timeout=None)
        self.questionnaire_id = questionnaire_id
        self.db = db
        self.opciones = opciones
        self.roles_ids = roles_ids
        self.multiple = multiple
        self.votos_usuarios = {}  # user_id: set de indices seleccionados
        self.message = None

        letras = ["🇦", "🇧", "🇨", "🇩", "🇪"]
        for i, op in enumerate(opciones):
            button = discord.ui.Button(
                label=f"{letras[i]} {op}"[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"quest:{questionnaire_id}:option:{i}"
            )
            button.callback = self.create_button_callback(i, op)
            self.add_item(button)

        # Si es de selección múltiple, añadimos un botón de confirmar
        if self.multiple:
            confirm_button = discord.ui.Button(
                label="✅ Confirmar Selección",
                style=discord.ButtonStyle.success,
                custom_id=f"quest:{questionnaire_id}:confirm"
            )
            confirm_button.callback = self.confirm_callback
            self.add_item(confirm_button)

    def create_button_callback(self, index: int, option_text: str):
        async def button_callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            
            if not self.multiple:
                # Modo Respuesta Única: Procesa al instante el voto y el rol
                role_id = self.roles_ids[index] if index < len(self.roles_ids) else None
                guild = interaction.guild
                member = interaction.user

                await self.db.save_questionnaire_vote(
                    self.questionnaire_id, user_id, json.dumps([index])
                )

                if role_id and role_id != guild.id:
                    role = guild.get_role(role_id)
                    if role:
                        try:
                            survey_roles = {
                                guild_role for guild_role_id in self.roles_ids
                                if guild_role_id and (guild_role := guild.get_role(guild_role_id)) is not None
                            }
                            stale_roles = [item for item in member.roles if item in survey_roles and item != role]
                            if role in member.roles:
                                await interaction.response.send_message(
                                    f"Ya tienes el rol **{role.name}**.", ephemeral=True
                                )
                            else:
                                await member.add_roles(role, reason="Selección de cuestionario")
                                if stale_roles:
                                    await member.remove_roles(*stale_roles, reason="Respuesta única de cuestionario")
                                await interaction.response.send_message(
                                    f"✨ Se asignó el rol **{role.name}**.", ephemeral=True
                                )
                            return
                        except (discord.Forbidden, discord.HTTPException):
                            await interaction.response.send_message("❌ Error al asignar el rol. Comprueba los permisos del bot.", ephemeral=True)
                            return
                
                await interaction.response.send_message(f"✅ Has votado por: **{option_text}**", ephemeral=True)
            else:
                selected = set(json.loads(await self.db.get_questionnaire_vote(self.questionnaire_id, user_id)))
                user_choices = selected
                if index in user_choices:
                    user_choices.remove(index)
                    await interaction.response.send_message(f"➖ Has desmarcado: **{option_text}**. Pulsa 'Confirmar Selección' cuando termines.", ephemeral=True)
                else:
                    user_choices.add(index)
                    await interaction.response.send_message(f"➕ Has marcado: **{option_text}**. Pulsa 'Confirmar Selección' cuando termines.", ephemeral=True)
                await self.db.save_questionnaire_vote(
                    self.questionnaire_id, user_id, json.dumps(sorted(user_choices))
                )

        return button_callback

    async def confirm_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        selected_indices = set(json.loads(
            await self.db.get_questionnaire_vote(self.questionnaire_id, user_id)
        ))
        if not selected_indices:
            await interaction.response.send_message("⚠️ No has seleccionado ninguna opción todavía.", ephemeral=True)
            return

        guild = interaction.guild
        member = interaction.user
        roles_aplicados = []
        selected_roles = set()

        for idx in selected_indices:
            role_id = self.roles_ids[idx] if idx < len(self.roles_ids) else None
            if role_id and role_id != guild.id:
                role = guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        roles_aplicados.append(role.name)
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                if role:
                    selected_roles.add(role)

        survey_roles = {
            guild_role for guild_role_id in self.roles_ids
            if guild_role_id and (guild_role := guild.get_role(guild_role_id)) is not None
        }
        stale_roles = [role for role in member.roles if role in survey_roles and role not in selected_roles]
        if stale_roles:
            try:
                await member.remove_roles(*stale_roles, reason="Selección múltiple de cuestionario")
            except (discord.Forbidden, discord.HTTPException):
                pass

        nombres_opciones = [self.opciones[i] for i in selected_indices]
        await interaction.response.send_message(
            f"✅ ¡Selección confirmada!\n• Opciones: **{', '.join(nombres_opciones)}**\n• Roles otorgados: **{', '.join(roles_aplicados) if roles_aplicados else 'Ninguno'}**",
            ephemeral=True
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class QuestionnairesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    async def cog_load(self):
        for questionnaire_id, message_id, options, config in await self.db.get_active_questionnaires():
            settings = json.loads(config or "{}")
            view = CuestionarioView(
                questionnaire_id,
                self.db,
                json.loads(options),
                settings.get("roles", []),
                settings.get("multiple", False),
            )
            self.bot.add_view(view, message_id=message_id)

    @app_commands.command(name="crear_cuestionario", description="Crea un cuestionario avanzado con roles automáticos y opciones múltiples.")
    async def crear_cuestionario(self, interaction: discord.Interaction):
        modal = CuestionarioModal(self.db)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(QuestionnairesCog(bot))