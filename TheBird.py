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

# --- SISTEMA INTERACTIVO CON SOPORTE MULTI-SELECCIÓN Y ROLES ---

class PreguntaSelect(discord.ui.Select):
    def __init__(self, pregunta_data, questionnaire_id, current_q_key, respuestas_usuario):
        self.questionnaire_id = questionnaire_id
        self.current_q_key = current_q_key
        self.respuestas_usuario = respuestas_usuario
        
        opciones_data = pregunta_data["opciones"]
        is_multiple = pregunta_data.get("multiple", False)
        
        max_val = len(opciones_data) if is_multiple and len(opciones_data) > 0 else 1
        if max_val > 25:
            max_val = 25

        options = [
            discord.SelectOption(label=op["label"], value=op["value"])
            for op in opciones_data
        ]
        
        placeholder_text = "Selecciona una opción..." if not is_multiple else "Selecciona una o varias opciones..."
        super().__init__(placeholder=placeholder_text, min_values=1, max_values=max_val, options=options)

    async def callback(self, interaction: discord.Interaction):
        datos = cargar_datos()
        cuestionario = datos[self.questionnaire_id]
        pregunta_actual = cuestionario["preguntas"][self.current_q_key]
        
        selecciones = self.values
        self.respuestas_usuario[self.current_q_key] = selecciones
        
        siguiente_key = None
        
        for seleccion in selecciones:
            for op in pregunta_actual["opciones"]:
                if op["value"] == seleccion:
                    if "role_id" in op and op["role_id"]:
                        role_id = op["role_id"]
                        role = interaction.guild.get_role(role_id)
                        if role:
                            try:
                                await interaction.user.add_roles(role)
                            except discord.Forbidden:
                                print(f"Aviso: El bot no tiene permisos suficientes para asignar el rol {role.name}.")
                    
                    if not siguiente_key and op.get("siguiente"):
                        siguiente_key = op.get("siguiente")

        if siguiente_key == "final" or not siguiente_key:
            if cuestionario.get("solo_una_vez", True):
                if "completados" not in cuestionario:
                    cuestionario["completados"] = []
                if interaction.user.id not in cuestionario["completados"]:
                    cuestionario["completados"].append(interaction.user.id)
                    guardar_datos(datos)

            embed = discord.Embed(
                title="Cuestionario Finalizado",
                description="Has completado todas las preguntas requeridas. ¡Gracias por participar!",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return

        siguiente_pregunta = cuestionario["preguntas"][siguiente_key]
        view = PreguntaView(siguiente_pregunta, self.questionnaire_id, siguiente_key, self.respuestas_usuario)
        
        embed = discord.Embed(
            title=cuestionario["titulo"],
            description=siguiente_pregunta["texto"],
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)

class PreguntaView(discord.ui.View):
    def __init__(self, pregunta_data, questionnaire_id, current_q_key, respuestas_usuario):
        super().__init__(timeout=180)
        self.add_item(PreguntaSelect(pregunta_data, questionnaire_id, current_q_key, respuestas_usuario))

class IniciarCuestionarioView(discord.ui.View):
    def __init__(self, questionnaire_id):
        super().__init__(timeout=None)
        self.questionnaire_id = questionnaire_id

    @discord.ui.button(label="Comenzar Cuestionario", style=discord.ButtonStyle.green, custom_id="start_survey")
    async def boton_comenzar(self, interaction: discord.Interaction, button: discord.ui.Button):
        datos = cargar_datos()
        cuestionario = datos.get(self.questionnaire_id)
        if not cuestionario:
            await interaction.response.send_message("Este cuestionario ya no existe.", ephemeral=True)
            return
        
        if cuestionario.get("solo_una_vez", True):
            if interaction.user.id in cuestionario.get("completados", []):
                await interaction.response.send_message("❌ Ya has completado este cuestionario anteriormente y no puedes volver a realizarlo.", ephemeral=True)
                return

        primera_key = "inicio"
        if primera_key not in cuestionario["preguntas"]:
            await interaction.response.send_message("Este cuestionario no tiene configurada una pregunta de 'inicio'.", ephemeral=True)
            return

        primera_pregunta = cuestionario["preguntas"][primera_key]
        respuestas_usuario = {}
        view = PreguntaView(primera_pregunta, self.questionnaire_id, primera_key, respuestas_usuario)
        
        embed = discord.Embed(
            title=cuestionario["titulo"],
            description=primera_pregunta["texto"],
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- VENTANA EMERGENTE MAESTRA (CREAR PREGUNTA Y OPCIONES DE GOLPE) ---

class CreacionCompletaModal(discord.ui.Modal, title="Crear Pregunta y Opciones"):
    id_cuest = discord.ui.TextInput(label="ID del Cuestionario (ej: staff)", placeholder="staff", required=True)
    titulo_cuest = discord.ui.TextInput(label="Título del Cuestionario (si es nuevo)", placeholder="Formulario de Staff", required=False)
    clave_preq = discord.ui.TextInput(label="Clave de la pregunta (ej: inicio, p_edad)", placeholder="inicio", required=True)
    texto_preq = discord.ui.TextInput(label="Enunciado de la pregunta", style=discord.TextStyle.paragraph, placeholder="¿Cuál es tu región?", required=True)
    opciones_bloque = discord.ui.TextInput(
        label="Opciones (Etiqueta | Valor | Siguiente)",
        style=discord.TextStyle.paragraph,
        placeholder="Europa | europa | p_edad\nAmérica | america | p_edad\nOtro | otro | final",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        datos = cargar_datos()
        id_c = self.id_cuest.value.strip()
        titulo = self.titulo_cuest.value.strip()
        clave_p = self.clave_preq.value.strip()

        # Si el cuestionario no existe, lo creamos base
        if id_c not in datos:
            if not titulo:
                titulo = "Cuestionario Interactivo"
            datos[id_c] = {
                "titulo": titulo,
                "descripcion": "Cuestionario interactivo",
                "solo_una_vez": True,
                "completados": [],
                "preguntas": {}
            }
        elif titulo:
            # Si ya existe pero pusieron título nuevo, lo actualizamos
            datos[id_c]["titulo"] = titulo

        # Procesar las opciones línea por línea
        lineas = self.opciones_bloque.value.strip().split("\n")
        opciones_lista = []

        for linea in lineas:
            partes = [p.strip() for p in linea.split("|")]
            if len(partes) >= 3:
                etiqueta, valor, siguiente = partes[0], partes[1], partes[2]
                
                # Crear rol automáticamente para esta opción
                try:
                    nuevo_rol = await interaction.guild.create_role(
                        name=etiqueta,
                        reason=f"Creado automáticamente mediante cuestionario ({id_c})"
                    )
                    role_id = nuevo_rol.id
                except discord.Forbidden:
                    role_id = None

                opciones_lista.append({
                    "label": etiqueta,
                    "value": valor,
                    "siguiente": siguiente,
                    "role_id": role_id
                })

        # Guardar la pregunta con sus opciones
        datos[id_c]["preguntas"][clave_p] = {
            "texto": self.texto_preq.value.strip(),
            "tipo": "select",
            "multiple": False,
            "opciones": opciones_lista
        }
        guardar_datos(datos)

        await interaction.response.send_message(
            f"✅ ¡Pregunta `{clave_p}` creada con éxito en el cuestionario **{id_c}** junto con sus {len(opciones_lista)} opciones y roles automáticos!",
            ephemeral=True
        )

# --- COMANDOS SLASH (/) DE GESTIÓN Y ELIMINACIÓN ---

@bot.tree.command(name="crear_pregunta", description="Abre una ventana para crear un cuestionario, pregunta y opciones de golpe.")
@app_commands.checks.has_permissions(administrator=True)
async def crear_pregunta(interaction: discord.Interaction):
    await interaction.response.send_modal(CreacionCompletaModal())

@bot.tree.command(name="borrar_pregunta", description="Elimina una pregunta entera de un cuestionario.")
@app_commands.describe(id_cuestionario="ID del cuestionario", clave_pregunta="Clave de la pregunta a borrar")
@app_commands.checks.has_permissions(administrator=True)
async def borrar_pregunta(interaction: discord.Interaction, id_cuestionario: str, clave_pregunta: str):
    datos = cargar_datos()
    if id_cuestionario not in datos or clave_pregunta not in datos[id_cuestionario]["preguntas"]:
        await interaction.response.send_message("❌ El cuestionario o la pregunta especificada no existen.", ephemeral=True)
        return
    del datos[id_cuestionario]["preguntas"][clave_pregunta]
    guardar_datos(datos)
    await interaction.response.send_message(f"🗑️ La pregunta `{clave_pregunta}` ha sido eliminada correctamente.", ephemeral=True)

@bot.tree.command(name="borrar_opcion", description="Elimina una opción concreta de una pregunta.")
@app_commands.describe(id_cuestionario="ID del cuestionario", clave_pregunta="Clave de la pregunta", valor_opcion="Valor interno de la opción a borrar")
@app_commands.checks.has_permissions(administrator=True)
async def borrar_opcion(interaction: discord.Interaction, id_cuestionario: str, clave_pregunta: str, valor_opcion: str):
    datos = cargar_datos()
    if id_cuestionario not in datos or clave_pregunta not in datos[id_cuestionario]["preguntas"]:
        await interaction.response.send_message("❌ El cuestionario o la pregunta no existen.", ephemeral=True)
        return
    
    opciones = datos[id_cuestionario]["preguntas"][clave_pregunta]["opciones"]
    nuevas_opciones = [op for op in opciones if op["value"] != valor_opcion]
    
    if len(opciones) == len(nuevas_opciones):
        await interaction.response.send_message(f"❌ No se encontró ninguna opción con el valor `{valor_opcion}`.", ephemeral=True)
        return
        
    datos[id_cuestionario]["preguntas"][clave_pregunta]["opciones"] = nuevas_opciones
    guardar_datos(datos)
    await interaction.response.send_message(f"🗑️ La opción con valor `{valor_opcion}` ha sido eliminada.", ephemeral=True)

@bot.tree.command(name="borrar_cuestionario", description="Elimina un cuestionario completo por su ID.")
@app_commands.describe(id_cuestionario="ID del cuestionario que deseas eliminar")
@app_commands.checks.has_permissions(administrator=True)
async def borrar_cuestionario(interaction: discord.Interaction, id_cuestionario: str):
    datos = cargar_datos()
    if id_cuestionario not in datos:
        await interaction.response.send_message("❌ No existe ningún cuestionario con ese ID.", ephemeral=True)
        return
    del datos[id_cuestionario]
    guardar_datos(datos)
    await interaction.response.send_message(f"🗑️ El cuestionario **{id_cuestionario}** ha sido eliminado por completo.", ephemeral=True)

@bot.tree.command(name="exportar_json", description="Muestra el JSON actual para guardar copias de seguridad.")
@app_commands.checks.has_permissions(administrator=True)
async def exportar_json(interaction: discord.Interaction):
    datos = cargar_datos()
    texto_json = json.dumps(datos, ensure_ascii=False, indent=4)
    if len(texto_json) > 1900:
        texto_json = texto_json[:1900] + "\n... (cortado)"
    await interaction.response.send_message(f"Copia de seguridad en JSON:\n```json\n{texto_json}\n```", ephemeral=True)

@bot.tree.command(name="publicar_cuestionario", description="Publica el cuestionario en un canal.")
@app_commands.describe(id_cuestionario="ID del cuestionario", canal="Canal de texto donde se publicará")
@app_commands.checks.has_permissions(administrator=True)
async def publicar_cuestionario(interaction: discord.Interaction, id_cuestionario: str, canal: discord.TextChannel):
    datos = cargar_datos()
    if id_cuestionario not in datos:
        await interaction.response.send_message("❌ El ID de cuestionario no existe.", ephemeral=True)
        return
    cuestionario = datos[id_cuestionario]
    embed = discord.Embed(title=cuestionario["titulo"], description="Haz clic en el botón de abajo para iniciar.", color=discord.Color.purple())
    view = IniciarCuestionarioView(id_cuestionario)
    await canal.send(embed=embed, view=view)
    await interaction.response.send_message(f"📢 Publicado correctamente en {canal.mention}.", ephemeral=True)

TOKEN = os.getenv("DISCORD_TOKEN")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)