import flet as ft
import os
import requests
import base64
import uuid
import threading
import time
from dotenv import load_dotenv

load_dotenv()

def main(page: ft.Page):
    page.title = "Generador de Imágenes IA"
    page.bgcolor = "#121212"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window.width = 1200
    page.window.height = 800
    page.window.maximized = True

    # --- ESTADO DE LA APLICACIÓN ---
    sesiones_chat = []
    sesion_activa = {"id": None}

    # --- SISTEMA DE NOTIFICACIÓN TOAST (Minimalista) ---
    toast_container = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.CHECK_CIRCLE, color="#4CAF50", size=20),
            ft.Text("Imagen guardada exitosamente", color="white", size=14)
        ]),
        bgcolor="#1E1E1E",
        padding=ft.padding.symmetric(horizontal=20, vertical=12),
        border_radius=30,
        border=ft.border.all(1, "#333333"),
        shadow=ft.BoxShadow(blur_radius=15, color=ft.colors.with_opacity(0.4, "black")),
        right=30,
        top=-100,
        animate_position=ft.animation.Animation(400, ft.AnimationCurve.EASE_OUT_BACK)
    )

    def mostrar_toast():
        toast_container.top = 30
        page.update()
        time.sleep(3)
        toast_container.top = -100
        page.update()

    # --- SISTEMA DE DESCARGA ---
    def guardar_imagen_local(e: ft.FilePickerResultEvent):
        if e.path:
            b64_data = page.session.get("img_descarga")
            if b64_data:
                with open(e.path, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                threading.Thread(target=mostrar_toast, daemon=True).start()

    file_picker = ft.FilePicker(on_result=guardar_imagen_local)
    page.overlay.append(file_picker)

    # --- VISOR DE IMÁGENES CON ZOOM ---
    def abrir_visor_imagen(b64_img):
        def descargar_desde_visor(e):
            page.session.set("img_descarga", b64_img)
            file_picker.save_file(dialog_title="Guardar imagen...", file_name="imagen_ia.png", allowed_extensions=["png"])

        def cerrar_visor(e):
            page.close(visor_dialog)

        # Estado del zoom
        zoom_state = {"factor": 1.0}
        base_size = 550 # Altura base de la imagen al abrir el panel

        img_control = ft.Image(
            src_base64=b64_img,
            height=base_size,
            fit=ft.ImageFit.CONTAIN
        )

        def actualizar_zoom():
            # Alteramos físicamente el tamaño para forzar a las barras de scroll a aparecer
            img_control.height = base_size * zoom_state["factor"]
            img_control.update()

        def zoom_in(e):
            if zoom_state["factor"] < 4.0: # Límite de 4x de zoom
                zoom_state["factor"] += 0.5
                actualizar_zoom()

        def zoom_out(e):
            if zoom_state["factor"] > 1.0: # No permitir hacerla más pequeña que el original
                zoom_state["factor"] -= 0.5
                actualizar_zoom()

        visor_dialog = ft.AlertDialog(
            content_padding=0,
            bgcolor="transparent",
            content=ft.Container(
                width=1000,
                height=700,
                bgcolor="#121212",
                border_radius=15,
                border=ft.border.all(1, "#333333"),
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                content=ft.Column([
                    # Fila superior de controles
                    ft.Container(
                        content=ft.Row([
                            ft.IconButton(ft.icons.ZOOM_OUT, on_click=zoom_out, icon_color="white", tooltip="Alejar"),
                            ft.IconButton(ft.icons.ZOOM_IN, on_click=zoom_in, icon_color="white", tooltip="Acercar"),
                            ft.Container(expand=True),
                            ft.IconButton(ft.icons.DOWNLOAD, on_click=descargar_desde_visor, icon_color="white", tooltip="Descargar imagen"),
                            ft.IconButton(ft.icons.CLOSE, on_click=cerrar_visor, icon_color="white", tooltip="Cerrar visor")
                        ]),
                        padding=10,
                        bgcolor="#181818" # Fondo oscuro sutil para la barra superior
                    ),
                    # Contenedores con scroll habilitado (Vertical y Horizontal)
                    ft.Container(
                        content=ft.Column([
                            ft.Row(
                                [img_control],
                                alignment=ft.MainAxisAlignment.CENTER,
                                scroll=ft.ScrollMode.AUTO
                            )
                        ], scroll=ft.ScrollMode.AUTO, alignment=ft.MainAxisAlignment.CENTER),
                        expand=True,
                        alignment=ft.alignment.center,
                        padding=20
                    )
                ])
            )
        )
        page.open(visor_dialog)

    # --- COMPONENTES VISUALES ---
    feed_chat = ft.ListView(expand=True, spacing=20, auto_scroll=False, padding=20)
    historial_lista = ft.ListView(expand=True, spacing=5)

    pantalla_bienvenida = ft.Container(
        content=ft.Column([
            ft.Icon(ft.icons.FORUM_OUTLINED, size=60, color="#333333"),
            ft.Text("Nueva Sesión", color="#555555", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Escribe un prompt abajo para comenzar un nuevo hilo.", color="#444444", size=14)
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        expand=True,
        alignment=ft.alignment.center,
        height=400
    )
    feed_chat.controls.append(pantalla_bienvenida)

    # --- LÓGICA DE INTERFAZ (RENDERIZADO) ---
    def renderizar_sidebar():
        historial_lista.controls.clear()
        for sesion in reversed(sesiones_chat):
            es_activa = (sesion["id"] == sesion_activa["id"])
            btn_sesion = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.CHAT_BUBBLE_OUTLINE, size=16, color="white" if es_activa else "#777777"),
                    ft.Text(sesion["titulo"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, size=14, color="white" if es_activa else "#AAAAAA", expand=True)
                ]),
                padding=10,
                bgcolor="#2A2A2A" if es_activa else "transparent",
                border_radius=8,
                ink=True,
                on_click=lambda e, sid=sesion["id"]: cambiar_sesion(sid)
            )
            historial_lista.controls.append(btn_sesion)
        page.update()

    def renderizar_mensaje_en_feed(prompt, b64):
        def trigger_descarga(e, b=b64):
            page.session.set("img_descarga", b)
            file_picker.save_file(dialog_title="Guardar imagen...", file_name="imagen_ia.png", allowed_extensions=["png"])

        def copiar_prompt(e, p=prompt):
            input_texto.value = p
            input_texto.focus()
            page.update()

        # Contenedor interactivo para la imagen en el feed
        imagen_clickable = ft.Container(
            content=ft.Image(src_base64=b64, height=450, fit=ft.ImageFit.CONTAIN, border_radius=10),
            ink=True,
            on_click=lambda e, b=b64: abrir_visor_imagen(b),
            border_radius=10,
            tooltip="Clic para ampliar y hacer zoom"
        )

        bloque_mensaje = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"Tú: {prompt}", color="#AAAAAA", italic=True, expand=True),
                    ft.IconButton(icon=ft.icons.EDIT, tooltip="Editar prompt", icon_color="#777777", icon_size=16, on_click=copiar_prompt),
                    ft.IconButton(icon=ft.icons.DOWNLOAD, tooltip="Descargar", icon_color="#777777", icon_size=16, on_click=trigger_descarga)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                imagen_clickable # Insertamos la imagen con el evento de clic
            ]),
            padding=15,
            bgcolor="#1E1E1E",
            border_radius=10,
            margin=ft.margin.only(bottom=10)
        )
        feed_chat.controls.append(bloque_mensaje)

    def cambiar_sesion(sid):
        sesion_activa["id"] = sid
        feed_chat.controls.clear()
        sesion = next((s for s in sesiones_chat if s["id"] == sid), None)
        if sesion:
            for msg in sesion["historial"]:
                renderizar_mensaje_en_feed(msg["prompt"], msg["b64"])
        renderizar_sidebar()
        page.update()
        feed_chat.scroll_to(offset=-1, duration=300)

    def nueva_sesion(e=None):
        sesion_activa["id"] = None
        feed_chat.controls.clear()
        feed_chat.controls.append(pantalla_bienvenida)
        renderizar_sidebar()
        input_texto.value = ""
        input_texto.focus()
        page.update()

    # --- PANELES ---
    btn_nueva_sesion = ft.ElevatedButton("Nuevo Chat", icon=ft.icons.ADD, on_click=nueva_sesion, bgcolor="#2A2A2A", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))

    panel_historial = ft.Container(
        content=ft.Column([
            btn_nueva_sesion,
            ft.Divider(color="#2A2A2A", height=20),
            ft.Text("Historial de Chats", weight=ft.FontWeight.BOLD, size=14, color="#AAAAAA"),
            historial_lista
        ]),
        width=260, bgcolor="#181818", border_radius=10, padding=15, margin=20
    )

    lienzo_imagen = ft.Container(
        content=feed_chat, expand=True, bgcolor="#0A0A0A", border_radius=15, border=ft.border.all(1, "#2A2A2A"), margin=ft.margin.only(top=20, right=20)
    )

    input_texto = ft.TextField(
        hint_text="Describe la imagen...", border_radius=30, filled=True, expand=True, border_color="transparent", bgcolor="#1E1E1E", content_padding=20,
        on_submit=lambda e: procesar_generacion()
    )

    def insertar_estilo(e):
        estilo = e.control.text
        texto_actual = input_texto.value.strip() if input_texto.value else ""
        input_texto.value = f"{texto_actual}, estilo {estilo}" if texto_actual else f"Estilo {estilo}"
        input_texto.focus()
        page.update()

    estilos = ["Fotorrealista", "Cyberpunk", "Sepia-Toned Vintage", "Minimalista", "Render 3D"]
    fila_chips = ft.Row([
        ft.ElevatedButton(text=estilo, bgcolor="#1E1E1E", color="#CCCCCC", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15), padding=ft.padding.symmetric(horizontal=15, vertical=0)), on_click=insertar_estilo) for estilo in estilos
    ], scroll=ft.ScrollMode.ADAPTIVE)

    # --- LÓGICA CENTRAL ---
    def procesar_generacion():
        prompt_final = input_texto.value.strip()
        if not prompt_final: return

        if sesion_activa["id"] is None:
            nuevo_id = str(uuid.uuid4())
            titulo = prompt_final[:30] + "..." if len(prompt_final) > 30 else prompt_final
            sesiones_chat.append({"id": nuevo_id, "titulo": titulo, "historial": []})
            sesion_activa["id"] = nuevo_id
            feed_chat.controls.clear()
            renderizar_sidebar()

        btn_enviar.disabled = True
        input_texto.disabled = True
        input_texto.value = ""

        bloque_carga = ft.Container(
            content=ft.Row([
                ft.ProgressRing(color="white", width=20, height=20),
                ft.Text(f"Generando: {prompt_final}", color="#AAAAAA", italic=True)
            ]),
            padding=15, bgcolor="#181818", border_radius=10, margin=ft.margin.only(bottom=10)
        )
        feed_chat.controls.append(bloque_carga)
        page.update()
        feed_chat.scroll_to(offset=-1, duration=300)

        try:
            endpoint = os.getenv("AZURE_AI_ENDPOINT")
            api_key = os.getenv("AZURE_AI_KEY")
            response = requests.post(endpoint, headers={"Content-Type": "application/json", "api-key": api_key}, json={"prompt": prompt_final, "model": "MAI-Image-2.5-Flash"})
            feed_chat.controls.remove(bloque_carga)

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    b64_img = data['data'][0].get('b64_json', '')
                    sesion = next((s for s in sesiones_chat if s["id"] == sesion_activa["id"]), None)
                    if sesion:
                        sesion["historial"].append({"prompt": prompt_final, "b64": b64_img})
                        renderizar_mensaje_en_feed(prompt_final, b64_img)
            else:
                feed_chat.controls.append(ft.Text(f"Error: {response.text}", color="red"))
        except Exception as ex:
            feed_chat.controls.append(ft.Text(f"Excepción: {ex}", color="red"))

        btn_enviar.disabled = False
        input_texto.disabled = False
        input_texto.focus()
        page.update()
        feed_chat.scroll_to(offset=-1, duration=400)

    btn_enviar = ft.IconButton(icon=ft.icons.AUTO_AWESOME, icon_color="white", bgcolor="#2A2A2A", icon_size=24, width=55, height=55, on_click=lambda e: procesar_generacion())

    panel_inferior = ft.Container(
        content=ft.Column([fila_chips, ft.Row([input_texto, btn_enviar], alignment=ft.MainAxisAlignment.CENTER)]),
        margin=ft.margin.only(right=20, bottom=20, top=10)
    )

    # --- CAPAS (Z-INDEX) ---
    layout_principal = ft.Row([
        panel_historial,
        ft.Column([
            lienzo_imagen,
            panel_inferior
        ], expand=True)
    ], expand=True)

    page.add(
        ft.Stack([
            layout_principal,
            toast_container
        ], expand=True)
    )

puerto_azure = int(os.environ.get("PORT", 8000))

ft.app(
    target=main,
    view=ft.WEB_BROWSER,
    host="0.0.0.0",
    port=puerto_azure
)
