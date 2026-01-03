/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DenominationView = publicWidget.Widget.extend({
    selector: '.cash_denomination_register_template',
    events: {
        'click .view-denomination-btn': '_toggleDenominationBox',
        'click .close-denomination-btn': '_closeDenominationBox',
    },

    _toggleDenominationBox(ev) {
        ev.stopPropagation();
        const button = ev.currentTarget;
        const hasLines = button.dataset.hasLines === 'true';
        const box = button.parentElement.querySelector('.denomination-box');
        
        if (!box) return;
        
        const msg = box.querySelector('.no-lines-message');
        const table = box.querySelector('.denomination-table');

        // Close any other open boxes
        document.querySelectorAll('.denomination-box').forEach(otherBox => {
            if (otherBox !== box) {
                otherBox.style.display = 'none';
            }
        });

        // Show appropriate content
        if (!hasLines) {
            if (table) table.style.display = 'none';
            if (msg) msg.style.display = 'block';
        } else {
            if (msg) msg.style.display = 'none';
            if (table) table.style.display = 'table';
        }

        // Toggle visibility
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

    _closeDenominationBox(ev) {
        ev.stopPropagation();
        const box = ev.currentTarget.closest('.denomination-box');
        if (box) {
            box.style.display = 'none';
        }
    },
});
