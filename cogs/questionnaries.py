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
        
        if len(lista_opciones) < 2 or len(lista_opciones) > 5:
            await interaction.response.send_message("❌ Debes introducir entre **2 y 5 opciones** válidas separadas por comas.", ephemeral=True)
            return

        is_multiple = self.multiple_seleccion.value.strip().lower() in ["sí", "si", "yes", "s"]

        # Crear automáticamente un rol en el servidor por cada opción introducida
        roles_creados_ids = []
        for op in lista_opciones:
            rol_existente = discord.utils.get(interaction.guild.roles, name=op)
            if not rol_existente:
                try:
                    nuevo_rol = await interaction.guild.create_role(name=op, reason=f"Creado por cuestionario de {interaction.user}")
                    roles_creados_ids.append(nuevo_rol.id)
                except Exception:
                    roles_creados_ids.append(None)
            else:
                roles_creados_ids.append(rol_existente.id)

        # Construir la vista interactiva
        view = CuestionarioView(lista_opciones, roles_creados_ids, is_multiple)

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

        await interaction.response.send_message("✅ ¡Cuestionario creado con éxito!", ephemeral=True)
        mensaje_publico = await interaction.channel.send(embed=embed, view=view)
        view.message = mensaje_publico


class CuestionarioView(discord.ui.View):
    def __init__(self, opciones: list, roles_ids: list, multiple: bool):
        super().__init__(timeout=None)
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
                custom_id=f"quest_opt_{i}"
            )
            button.callback = self.create_button_callback(i, op)
            self.add_item(button)

        # Si es de selección múltiple, añadimos un botón de confirmar
        if self.multiple:
            confirm_button = discord.ui.Button(
                label="✅ Confirmar Selección",
                style=discord.ButtonStyle.success,
                custom_id="quest_confirm"
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

                if role_id:
                    role = guild.get_role(role_id)
                    if role:
                        try:
                            if role in member.roles:
                                await member.remove_roles(role)
                                await interaction.response.send_message(f"🔄 Te has quitado el rol **{role.name}**.", ephemeral=True)
                                return
                            else:
                                await member.add_roles(role)
                                await interaction.response.send_message(f"✨ ¡Se te ha asignado el rol **{role.name}**!", ephemeral=True)
                                return
                        except Exception:
                            await interaction.response.send_message("❌ Error al asignar el rol. Comprueba los permisos del bot.", ephemeral=True)
                            return
                
                await interaction.response.send_message(f"✅ Has votado por: **{option_text}**", ephemeral=True)
            else:
                # Modo Selección Múltiple: Alterna la selección localmente para el usuario antes de confirmar
                if user_id not in self.votos_usuarios:
                    self.votos_usuarios[user_id] = set()
                
                user_choices = self.votos_usuarios[user_id]
                if index in user_choices:
                    user_choices.remove(index)
                    await interaction.response.send_message(f"➖ Has desmarcado: **{option_text}**. Pulsa 'Confirmar Selección' cuando termines.", ephemeral=True)
                else:
                    user_choices.add(index)
                    await interaction.response.send_message(f"➕ Has marcado: **{option_text}**. Pulsa 'Confirmar Selección' cuando termines.", ephemeral=True)

        return button_callback

    async def confirm_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id not in self.votos_usuarios or not self.votos_usuarios[user_id]:
            await interaction.response.send_message("⚠️ No has seleccionado ninguna opción todavía.", ephemeral=True)
            return

        selected_indices = self.votos_usuarios[user_id]
        guild = interaction.guild
        member = interaction.user
        roles_aplicados = []

        for idx in selected_indices:
            role_id = self.roles_ids[idx] if idx < len(self.roles_ids) else None
            if role_id:
                role = guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        roles_aplicados.append(role.name)
                    except Exception:
                        pass

        nombres_opciones = [self.opciones[i] for i in selected_indices]
        await interaction.response.send_message(
            f"✅ ¡Selección confirmada!\n• Opciones: **{', '.join(nombres_opciones)}**\n• Roles otorgados: **{', '.join(roles_aplicados) if roles_aplicados else 'Ninguno'}**",
            ephemeral=True
        )


class QuestionnairesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name="crear_cuestionario", description="Crea un cuestionario avanzado con roles automáticos y opciones múltiples.")
    async def crear_cuestionario(self, interaction: discord.Interaction):
        modal = CuestionarioModal(self.db)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(QuestionnairesCog(bot))