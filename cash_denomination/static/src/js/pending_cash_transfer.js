/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.PendingCashTransfer = publicWidget.Widget.extend({
    selector: '.pending_cash_transfer_template',

    events: {
        'click .reject-btn': '_openRejectModal',
        'click .submit-reject-btn': '_rejectTransferAmount',
        'click .approve-btn': '_acceptTransferAmount',
        'change #all_counter': '_onCounterChange',
    },

    _openRejectModal(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const modal = bootstrap.Modal.getOrCreateInstance(
            document.getElementById('rejectReasonModal')
        );
        if (modal) modal.show();
    },

    async _rejectTransferAmount(ev) {
        ev.preventDefault();
        ev.stopPropagation();

        const ctNumberEl = document.getElementById('ct_number');
        const reasonEl = document.querySelector('.reject-reason');
        
        const ctNumber = ctNumberEl?.textContent?.trim();
        const reason = reasonEl?.value?.trim();

        if (!ctNumber) {
            alert('No transfer selected');
            return;
        }

        try {
            await rpc('/cash/transfer/amount/reject', {
                transfer_number: ctNumber,
                reject_reason: reason || 'No reason provided',
            });
            
            const modal = bootstrap.Modal.getInstance(
                document.getElementById('rejectReasonModal')
            );
            if (modal) modal.hide();
            
            window.location.href = '/pending/cash/transfer';
        } catch (err) {
            console.error('Error rejecting transfer:', err);
            alert('Failed to reject transfer. Please try again.');
        }
    },

    async _onCounterChange(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        
        const counterId = parseInt(ev.currentTarget.value);
        if (!counterId) return;

        try {
            const result = await rpc('/check/cash/transfer/by/counter', {
                counter_id: counterId,
            });

            // Clear previous data
            this._clearTransferDetails();

            const transferData = result.transfer_list || [];
            if (transferData.length === 0) {
                this._showNoTransfersMessage();
                return;
            }

            // Display first transfer (or could iterate for multiple)
            transferData.forEach(data => {
                this._displayTransferDetails(data);
            });
        } catch (err) {
            console.error('Error fetching transfers:', err);
        }
    },

    _clearTransferDetails() {
        const fields = ['ct_date', 'ct_number', 'ct_from_user', 'ct_from_counter', 'ct_to_counter'];
        fields.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
        
        const tbody = document.getElementById('denomination_tbody');
        if (tbody) tbody.innerHTML = '';
        
        const total = document.getElementById('denomination_total');
        if (total) total.textContent = '0.00';
    },

    _showNoTransfersMessage() {
        const tbody = document.getElementById('denomination_tbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No pending transfers for this counter</td></tr>';
        }
    },

    _displayTransferDetails(data) {
        const setTextContent = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        };

        setTextContent('ct_date', data.date);
        setTextContent('ct_number', data.name);
        setTextContent('ct_from_user', data.from_user);
        setTextContent('ct_from_counter', data.from_counter);
        setTextContent('ct_to_counter', data.to_counter);

        const denominations = data.denomination_list || [];
        const tbody = document.getElementById('denomination_tbody');
        const totalEl = document.getElementById('denomination_total');

        if (!tbody) return;

        tbody.innerHTML = '';
        let grandTotal = 0;

        denominations.forEach(den => {
            grandTotal += den.total;
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>INR</td>
                <td>${den.amount}</td>
                <td>${den.counts}</td>
                <td>${den.total.toFixed(2)}</td>
            `;
            tbody.appendChild(row);
        });

        if (totalEl) {
            totalEl.textContent = grandTotal.toFixed(2);
        }
    },

    async _acceptTransferAmount(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        
        const ctNumberEl = document.getElementById('ct_number');
        const ctNumber = ctNumberEl?.textContent?.trim();
        
        if (!ctNumber) {
            alert('No transfer selected. Please select a counter first.');
            return;
        }

        try {
            const result = await rpc('/cash/transfer/amount/accept', {
                counter_name: ctNumber,
            });
            
            if (result.error) {
                alert(result.error);
                return;
            }
            
            window.location.href = '/cash/transfer/accepted';
        } catch (err) {
            console.error('Error accepting transfer:', err);
            alert('Failed to accept transfer. Please try again.');
        }
    },
});
