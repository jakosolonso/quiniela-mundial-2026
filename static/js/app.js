let usuarioActual = null;

// Cargar datos al iniciar
document.addEventListener('DOMContentLoaded', () => {
    cargarDatosIniciales();
    cargarPartidos();
    cargarTablaPosiciones();
});

// ============ FUNCIONES DE USUARIO ============
async function crearUsuario() {
    const nombre = document.getElementById('userName').value.trim();
    const email = document.getElementById('userEmail').value.trim();
    
    if (!nombre || !email) {
        alert('Por favor completa todos los campos');
        return;
    }
    
    try {
        const response = await fetch('/api/usuarios', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({nombre, email})
        });
        
        const data = await response.json();
        usuarioActual = {id: data.id, nombre, email};
        
        document.getElementById('userInfo').style.display = 'block';
        document.getElementById('displayName').textContent = nombre;
        document.querySelector('.user-form').style.display = 'none';
        
        cargarMisPronosticos();
        cargarTablaPosiciones();
    } catch (error) {
        console.error('Error:', error);
        alert('Error al crear usuario');
    }
}

// Cargar usuario actual
async function cargarUsuarioActual() {
    try {
        const response = await fetch('/api/usuario-actual');
        if (response.ok) {
            const usuario = await response.json();
            document.getElementById('userNameHeader').textContent = usuario.nombre;
        } else {
            window.location.href = '/login';
        }
    } catch (error) {
        window.location.href = '/login';
    }
}

async function cerrarSesion() {
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/login';
}

// Llamar al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    cargarUsuarioActual();
    // ... resto de tus funciones
});

function cambiarUsuario() {
    usuarioActual = null;
    document.getElementById('userInfo').style.display = 'none';
    document.querySelector('.user-form').style.display = 'flex';
    document.getElementById('userName').value = '';
    document.getElementById('userEmail').value = '';
}

// ============ CARGAR PARTIDOS ============
async function cargarPartidos() {
    try {
        const response = await fetch('/api/partidos');
        const partidos = await response.json();
        
        // Mostrar en pestaña de pronósticos
        const pronosticosDiv = document.getElementById('partidosList');
        pronosticosDiv.innerHTML = partidos.map(partido => renderPartidoCard(partido, true)).join('');
        
        // Mostrar en pestaña de resultados
        const resultadosDiv = document.getElementById('resultadosList');
        resultadosDiv.innerHTML = partidos.map(partido => renderPartidoCard(partido, false)).join('');
        
    } catch (error) {
        console.error('Error:', error);
    }
}

function renderPartidoCard(partido, editable) {
    const fecha = new Date(partido.fecha);
    const fechaStr = fecha.toLocaleDateString('es-ES', {day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'});
    
    let resultadoHtml = '';
    if (partido.jugado) {
        resultadoHtml = `
            <div class="resultado">
                Resultado oficial: ${partido.resultado_local} - ${partido.resultado_visitante}
            </div>
        `;
    }
    
    let pronosticoHtml = '';
    if (editable && !partido.jugado) {
        pronosticoHtml = `
            <div class="pronostico-form">
                <input type="number" id="gol_local_${partido.id}" placeholder="Goles local" min="0" max="20">
                <span>vs</span>
                <input type="number" id="gol_visit_${partido.id}" placeholder="Goles visitante" min="0" max="20">
            </div>
            <button onclick="guardarPronostico(${partido.id})" class="btn-guardar">Guardar Pronóstico</button>
        `;
    } else if (editable && partido.jugado) {
        pronosticoHtml = `<div class="puntos">✅ Partido finalizado</div>`;
    }
    
    return `
        <div class="partido-card ${partido.jugado ? 'jugado' : ''}">
            <div class="partido-info">
                <div class="fecha">${fechaStr}</div>
                <div class="grupo">Grupo ${partido.grupo}</div>
                <div class="equipos">
                    ${partido.equipo_local} vs ${partido.equipo_visitante}
                </div>
            </div>
            ${resultadoHtml}
            ${pronosticoHtml}
        </div>
    `;
}

// ============ GUARDAR PRONÓSTICOS ============
async function guardarPronostico(partidoId) {
    if (!usuarioActual) {
        alert('Primero regístrate o selecciona un usuario');
        return;
    }
    
    const golesLocal = parseInt(document.getElementById(`gol_local_${partidoId}`).value);
    const golesVisitante = parseInt(document.getElementById(`gol_visit_${partidoId}`).value);
    
    if (isNaN(golesLocal) || isNaN(golesVisitante)) {
        alert('Por favor ingresa los goles para ambos equipos');
        return;
    }
    
    try {
        const response = await fetch('/api/pronosticos', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                usuario_id: usuarioActual.id,
                partido_id: partidoId,
                goles_local: golesLocal,
                goles_visitante: golesVisitante
            })
        });
        
        if (response.ok) {
            alert('✅ Pronóstico guardado correctamente');
            cargarMisPronosticos();
        } else {
            alert('Error al guardar el pronóstico');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al conectar con el servidor');
    }
}

async function cargarMisPronosticos() {
    if (!usuarioActual) return;
    
    try {
        const response = await fetch(`/api/pronosticos/usuario/${usuarioActual.id}`);
        const pronosticos = await response.json();
        
        // Actualizar los inputs con los pronósticos existentes
        pronosticos.forEach(p => {
            const localInput = document.getElementById(`gol_local_${p.partido_id}`);
            const visitInput = document.getElementById(`gol_visit_${p.partido_id}`);
            if (localInput && visitInput) {
                localInput.value = p.goles_local;
                visitInput.value = p.goles_visitante;
            }
        });
    } catch (error) {
        console.error('Error:', error);
    }
}

// ============ TABLA DE POSICIONES ============
async function cargarTablaPosiciones() {
    try {
        const response = await fetch('/api/tabla-posiciones');
        const tabla = await response.json();
        
        const tablaHtml = `
            <table class="tabla-posiciones">
                <thead>
                    <tr><th>Posición</th><th>Jugador</th><th>Puntos</th></tr>
                </thead>
                <tbody>
                    ${tabla.map((item, index) => `
                        <tr>
                            <td>${index + 1}</td>
                            <td>${item.nombre}</td>
                            <td><strong>${item.puntos}</strong></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        
        document.getElementById('tablaPosiciones').innerHTML = tablaHtml;
    } catch (error) {
        console.error('Error:', error);
    }
}

// ============ DATOS INICIALES ============
async function cargarDatosIniciales() {
    try {
        await fetch('/api/cargar-datos-iniciales', {method: 'POST'});
        console.log('✅ Datos iniciales cargados');
    } catch (error) {
        console.error('Error cargando datos iniciales:', error);
    }
}

function togglePassword(inputId, icon) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// ============ CAMBIAR PESTAÑAS ============
function cambiarTab(tab) {
    // Ocultar todas las pestañas
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Desactivar todos los botones
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Mostrar la pestaña seleccionada
    document.getElementById(`${tab}Tab`).classList.add('active');
    
    // Actualizar datos según la pestaña
    if (tab === 'tabla') {
        cargarTablaPosiciones();
    } else if (tab === 'pronosticos' && usuarioActual) {
        cargarMisPronosticos();
    }
}