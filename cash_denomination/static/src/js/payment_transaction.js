/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.TransferView = publicWidget.Widget.extend({
    selector: '.cash_transfer_register_template',
    events: {
        'click .view-transfer-btn': '_toggleTransferBox',
        'click .close-transfer-btn': '_closeTransferBox',
    },

    _toggleTransferBox(ev) {
        ev.stopPropagation();

        const button = ev.currentTarget;
        const box = button.parentElement.querySelector('.transfer-box');
        const hasLines = button.dataset.hasLines === 'true';

        if (!box) return;

        const msg = box.querySelector('.no-transfer-lines');
        const table = box.querySelector('.transfer-table');

        // Hide all other open boxes
        document.querySelectorAll('.transfer-box').forEach(otherBox => {
            if (otherBox !== box) {
                otherBox.style.display = 'none';
            }
        });

        // Show only message or table
        if (!hasLines) {
            if (table) table.style.display = 'none';
            if (msg) msg.style.display = 'block';
        } else {
            if (msg) msg.style.display = 'none';
            if (table) table.style.display = 'table';
        }

        // Toggle the selected box
        box.style.display = box.style.display === 'none' ? 'block' : 'none';

        // Close when clicking outside
        const closeHandler = (e) => {
            if (!box.contains(e.target) && e.target !== button) {
                box.style.display = 'none';
                document.removeEventListener('click', closeHandler);
            }
        };
        
        setTimeout(() => {
            document.addEventListener('click', closeHandler);
        }, 0);
    },

    _closeTransferBox(ev) {
        ev.stopPropagation();
        const box = ev.currentTarget.closest('.transfer-box');
        if (box) {
            box.style.display = 'none';
        }
    },
});
