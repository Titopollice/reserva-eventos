const socket = io();

// Adicionar novo evento
document.getElementById('add-event-btn').addEventListener('click', () => {
    const name = document.getElementById('new-event-name').value;
    const slots = parseInt(document.getElementById('new-event-slots').value);
    
    if (name && slots > 0) {
        socket.emit('add_event', { name, slots });
        document.getElementById('new-event-name').value = '';
        document.getElementById('new-event-slots').value = '';
    } else {
        alert('Por favor, preencha todos os campos corretamente.');
    }
});

// Atualizar eventos existentes
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('save-btn')) {
        const card = e.target.closest('.event-card');
        const id = parseInt(card.getAttribute('data-id'));
        const name = card.querySelector('.event-name').value;
        const slots = parseInt(card.querySelector('.event-slots').value);
        
        socket.emit('update_event', { id, name, slots });
    }
    
    if (e.target.classList.contains('delete-btn')) {
        if (confirm('Tem certeza que deseja excluir este evento?')) {
            const card = e.target.closest('.event-card');
            const id = parseInt(card.getAttribute('data-id'));
            socket.emit('delete_event', { id });
        }
    }
});

// Atualizar interface quando houver mudanças
socket.on('update_events', (events) => {
    const container = document.getElementById('events-admin');
    container.innerHTML = '<h2>Eventos Existentes</h2>';
    
    events.forEach(event => {
        const card = document.createElement('div');
        card.className = 'event-card admin-card';
        card.setAttribute('data-id', event.id);
        card.innerHTML = `
            <input type="text" class="event-name" value="${event.name}">
            <input type="number" class="event-slots" value="${event.slots}">
            <div class="admin-buttons">
                <button class="save-btn">Salvar</button>
                <button class="delete-btn">Excluir</button>
            </div>
        `;
        container.appendChild(card);
    });
}); 