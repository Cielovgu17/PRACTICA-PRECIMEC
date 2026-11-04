"""Contenido inicial. Todo queda marcado como ejemplo y es editable desde el administrador."""
import secrets
from pathlib import Path

from . import auth, content

SAMPLE_INTRO = (
    "Contenido de ejemplo. Aquí irá la descripción introductoria de la técnica, "
    "aprobada por PRECIMEC."
)
SAMPLE_SYSTEM = (
    "Contenido de ejemplo. Aquí irá la información general del sistema de osteosíntesis, "
    "aprobada por PRECIMEC."
)

# Títulos provisionales de navegación. No son una secuencia clínica definitiva.
STEPS = [
    ("Posicionamiento del paciente", [
        "Preparación de la mesa quirúrgica",
        "Posicionamiento del paciente",
        "Verificación de la posición",
        "Preparación del campo quirúrgico",
    ]),
    ("Preparación y abordaje quirúrgico", None),
    ("Punto de entrada", None),
    ("Introducción de la guía", None),
    ("Preparación del canal femoral", None),
    ("Inserción del clavo cefalomedular", None),
    ("Colocación del elemento cefálico", None),
    ("Bloqueo distal", None),
    ("Verificación y finalización", None),
]
PLACEHOLDER_SUBSTEPS = ["Subpaso provisional A", "Subpaso provisional B"]

# Nombres tomados de los archivos STL del proyecto. Falta que PRECIMEC los verifique;
# no se les asigna función ni paso para no atribuirles un uso clínico sin confirmar.
INSTRUMENTS = [
    "Abridor canulado del canal medular",
    "Broca canulada compatible con guía de 2,5 mm",
    "Escariador flexible canulado",
    "Guía de punta olivada de 2,5 × 800 mm",
    "Hoja helicoidal de 10,5 × 75 mm",
    "Llave combinada",
    "Mango de conexión",
    "Martillo del sistema de clavo cefalomedular",
    "Medidor de profundidad",
    "Plantilla radiográfica",
    "Protector de tejidos",
    "Tornillo cortical",
]
SAMPLE_INSTRUMENT = "Contenido de ejemplo. Descripción pendiente de aprobación por PRECIMEC."


def _sample_fields(title: str) -> tuple:
    return (
        f"Contenido de ejemplo. Aquí irá el objetivo aprobado de «{title}».",
        "Contenido de ejemplo. Aquí irá la descripción aprobada de este paso.",
        "Contenido de ejemplo. Aquí irá el desarrollo del procedimiento, cuando PRECIMEC lo apruebe.",
        "Contenido de ejemplo. Aquí irán las observaciones importantes.",
        "Contenido de ejemplo. Aquí irán las recomendaciones para el instrumentador.",
    )


def _insert_step(conn, parent_id, position: int, title: str) -> int:
    cur = conn.execute(
        """INSERT INTO steps (parent_id, position, title, objective, description, procedure,
           observations, recommendations, is_sample) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (parent_id, position, title, *_sample_fields(title)),
    )
    return cur.lastrowid


def seed_content(conn) -> None:
    if conn.execute("SELECT 1 FROM technique").fetchone():
        return
    conn.execute(
        "INSERT INTO technique (id, company, platform_name, name, intro, system_info, is_sample) "
        "VALUES (1, 'PRECIMEC', 'Instructivo quirúrgico', 'Clavo cefalomedular', ?, ?, 1)",
        (SAMPLE_INTRO, SAMPLE_SYSTEM),
    )
    for index, (title, substeps) in enumerate(STEPS):
        step_id = _insert_step(conn, None, index, title)
        for sub_index, sub_title in enumerate(substeps or PLACEHOLDER_SUBSTEPS):
            _insert_step(conn, step_id, sub_index, sub_title)
    for name in INSTRUMENTS:
        conn.execute("INSERT INTO instruments (name, description) VALUES (?, ?)", (name, SAMPLE_INSTRUMENT))
    conn.commit()
    content.publish(conn, "Contenido inicial")


def seed_users(conn, data_dir: Path) -> None:
    """Crea las cuentas iniciales con contraseñas al azar y las deja en un archivo local."""
    if conn.execute("SELECT 1 FROM users").fetchone():
        return
    accounts = [
        ("admin@precimec.local", "Administración PRECIMEC", "admin"),
        ("consulta@precimec.local", "Instrumentador de prueba", "consulta"),
    ]
    lines = ["Cuentas iniciales de la plataforma. Cambia estas contraseñas en Mi perfil.", ""]
    for email, name, role in accounts:
        password = secrets.token_urlsafe(12)
        conn.execute(
            "INSERT INTO users (email, name, role, password_hash) VALUES (?, ?, ?, ?)",
            (email, name, role, auth.hash_password(password)),
        )
        lines += [f"Rol: {role}", f"Correo: {email}", f"Contraseña: {password}", ""]
    conn.commit()
    (data_dir / "credenciales-iniciales.txt").write_text("\n".join(lines), encoding="utf-8")
