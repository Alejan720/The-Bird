from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot activo"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

import json
import os
import discord
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "cuestionarios.json"

def cargar_datos():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_datos(datos):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comandos slash.")
    except Exception as e:
        print(e)
    print(f"Bot conectado como {bot.user}")

# --- SISTEMA INTERACTIVO CON ASIGNACIÓN DE ROLES ---

class PreguntaSelect(discord.ui.Select):
    def __init__(self, opciones_data, questionnaire_id, current_q_key, respuestas_usuario):
        self.questionnaire_id = questionnaire_id
        self.current_q_key = current_q_key
        self.respuestas_usuario = respuestas_usuario
        
        options = [
            discord.SelectOption(label=op["label"], value=op["value"])
            for op in opciones_data
        ]
        super().__init__(placeholder="Selecciona una opción...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        datos = cargar_datos()
        cuestionario = datos[self.questionnaire_id]
        pregunta_actual = cuestionario["preguntas"][self.current_q_key]
        
        seleccion = self.values[0]
        self.respuestas_usuario[self.current_q_key] = seleccion
        
        siguiente_key = None
        opcion_seleccionada = None
        for op in pregunta_actual["opciones"]:
            if op["value"] == seleccion:
                siguiente_key = op.get("siguiente")
                opcion_seleccionada = op
                break

        # Asignar rol automáticamente si la opción tiene un rol vinculado
        if opcion_seleccionada and "role_id" in opcion_seleccionada:
            role_id = opcion_seleccionada["role_id"]
            role = interaction.guild.get_role(role_id)
            if role:
                try:
                    await interaction.user.add_roles(role)
                except discord.Forbidden:
                    print(f"Aviso: El bot no tiene permisos suficientes para asignar el rol {role.name}.")

        if siguiente_key == "final" or not siguiente_key:
            embed = discord.Embed(
                title="Cuestionario Finalizado",
                description="Has completado todas las preguntas requeridas. ¡Gracias por participar!",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            print(f"Respuestas de {interaction.user}: {self.respuestas_usuario}")
            return

        siguiente_pregunta = cuestionario["preguntas"][siguiente_key]
        view = PreguntaView(siguiente_pregunta["opciones"], self.questionnaire_id, siguiente_key, self.respuestas_usuario)
        
        embed = discord.Embed(
            title=cuestionario["titulo"],
            description=siguiente_pregunta["texto"],
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)

class PreguntaView(discord.ui.View):
    def __init__(self, opciones_data, questionnaire_id, current_q_key, respuestas_usuario):
        super().__init__(timeout=180)
        self.add_item(PreguntaSelect(opciones_data, questionnaire_id, current_q_key, respuestas_usuario))

class IniciarCuestionarioView(discord.ui.View):
    def __init__(self, questionnaire_id):
        super().__init__(timeout=None)
        self.questionnaire_id = questionnaire_id

    @discord.ui.button(label="Comenzar Cuestionario", style=discord.ButtonStyle.green, custom_id="start_survey")
    async def boton_comenzar(self, interaction: discord.Interaction, button: discord.ui.Button):
        datos = cargar_datos()
        cuestionario = datos[self.questionnaire_id]
        
        primera_key = "inicio"
        if primera_key not in cuestionario["preguntas"]:
            await interaction.response.send_message("Este cuestionario no tiene configurada una pregunta de 'inicio'.", ephemeral=True)
            return

        primera_pregunta = cuestionario["preguntas"][primera_key]
        respuestas_usuario = {}
        view = PreguntaView(primera_pregunta["opciones"], self.questionnaire_id, primera_key, respuestas_usuario)
        
        embed = discord.Embed(
            title=cuestionario["titulo"],
            description=primera_pregunta["texto"],
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- COMANDOS SLASH (/) CON CREACIÓN AUTOMÁTICA DE ROLES ---

@bot.tree.command(name="crear_cuestionario", description="Crea un nuevo cuestionario base.")
@app_commands.describe(
    id_cuestionario="Identificador único sin espacios (ej: staff_r4arena)",
    titulo="Título principal que mostrará el cuestionario"
)
@app_commands.checks.has_permissions(administrator=True)
async def crear_cuestionario(interaction: discord.Interaction, id_cuestionario: str, titulo: str):
    datos = cargar_datos()
    if id_cuestionario in datos:
        await interaction.response.send_message("Ya existe un cuestionario con ese ID.", ephemeral=True)
        return
    
    datos[id_cuestionario] = {
        "titulo": titulo,
        "descripcion": "Cuestionario interactivo",
        "preguntas": {}
    }
    guardar_datos(datos)
    await interaction.response.send_message(f"Cuestionario **{id_cuestionario}** creado. Usa `/agregar_pregunta` para continuar.", ephemeral=True)

@bot.tree.command(name="agregar_pregunta", description="Añade una pregunta al cuestionario.")
@app_commands.describe(
    id_cuestionario="ID del cuestionario",
    clave_pregunta="Usa 'inicio' para la primera, o un nombre clave (ej: p_torneos)",
    texto="El texto o enunciado de la pregunta"
)
@app_commands.checks.has_permissions(administrator=True)
async def agregar_pregunta(interaction: discord.Interaction, id_cuestionario: str, clave_pregunta: str, texto: str):
    datos = cargar_datos()
    if id_cuestionario not in datos:
        await interaction.response.send_message("El ID de cuestionario no existe.", ephemeral=True)
        return
    
    datos[id_cuestionario]["preguntas"][clave_pregunta] = {
        "texto": texto,
        "tipo": "select",
        "opciones": []
    }
    guardar_datos(datos)
    await interaction.response.send_message(f"Pregunta `{clave_pregunta}` añadida. Ahora añade opciones con `/agregar_opcion`.", ephemeral=True)

@bot.tree.command(name="agregar_opcion", description="Añade una opción, crea un rol automático con su nombre y configura su salto.")
@app_commands.describe(
    id_cuestionario="ID del cuestionario",
    clave_pregunta="Clave de la pregunta a la que pertenece esta opción",
    etiqueta="Texto visible (servirá también como nombre del rol a crear)",
    valor="Valor interno de la respuesta",
    siguiente_clave="Clave de la siguiente pregunta o escribe 'final'"
)
@app_commands.checks.has_permissions(administrator=True, manage_roles=True)
async def agregar_opcion(interaction: discord.Interaction, id_cuestionario: str, clave_pregunta: str, etiqueta: str, valor: str, siguiente_clave: str):
    datos = cargar_datos()
    if id_cuestionario not in datos or clave_pregunta not in datos[id_cuestionario]["preguntas"]:
        await interaction.response.send_message("El cuestionario o la pregunta especificada no existen.", ephemeral=True)
        return
    
    # Crear el rol automáticamente en el servidor de Discord
    try:
        nuevo_rol = await interaction.guild.create_role(
            name=etiqueta, 
            reason=f"Creado automáticamente mediante cuestionario ({id_cuestionario})"
        )
    except discord.Forbidden:
        await interaction.response.send_message("Error: El bot no tiene permisos para crear roles (asegúrate de que el rol del bot esté por encima en la lista de roles).", ephemeral=True)
        return
    
    opcion = {
        "label": etiqueta,
        "value": valor,
        "siguiente": siguiente_clave,
        "role_id": nuevo_rol.id  # Guardamos el ID del rol creado
    }
    
    datos[id_cuestionario]["preguntas"][clave_pregunta]["opciones"].append(opcion)
    guardar_datos(datos)
    
    await interaction.response.send_message(
        f"Opción **{etiqueta}** añadida.\n"
        f"• Rol creado automáticamente: {nuevo_rol.mention}\n"
        f"• Salto configurado hacia: `{siguiente_clave}`",
        ephemeral=True
    )

@bot.tree.command(name="publicar_cuestionario", description="Publica el cuestionario y su botón de inicio en un canal.")
@app_commands.describe(
    id_cuestionario="ID del cuestionario a publicar",
    canal="Canal de texto donde se enviará el mensaje"
)
@app_commands.checks.has_permissions(administrator=True)
async def publicar_cuestionario(interaction: discord.Interaction, id_cuestionario: str, canal: discord.TextChannel):
    datos = cargar_datos()
    if id_cuestionario not in datos:
        await interaction.response.send_message("El ID de cuestionario no existe.", ephemeral=True)
        return

    cuestionario = datos[id_cuestionario]
    
    embed = discord.Embed(
        title=cuestionario["titulo"],
        description="Haz clic en el botón de abajo para iniciar el cuestionario de forma privada.",
        color=discord.Color.purple()
    )
    
    view = IniciarCuestionarioView(id_cuestionario)
    await canal.send(embed=embed, view=view)
    await interaction.response.send_message(f"Cuestionario publicado correctamente en {canal.mention}.", ephemeral=True)

TOKEN = os.getenv("DISCORD_TOKEN")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)