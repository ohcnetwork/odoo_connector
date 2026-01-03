/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.CounterCashDenomination = publicWidget.Widget.extend({
    selector: '.cash_denomination_template',
    events: {
        'change #counter': '_onCounterChange',
        'click #cash_transfer_btn': '_OpenTransferCashModal',
        'input .counts-input': '_onDenominationChange',
        'input .transfer-counts-input': '_onTransferDenominationChange',
        'submit #cash_denomination_form': '_CashDenominationSubmit',
        'submit #mismatch-submit-modal': '_MismatchCashDenominationSubmit',
        'submit #cash_tranfer_form': '_onTransferSubmit',
    },

    start() {
        this._setCurrentDate();
        // Auto-select first counter if only one exists
        const counterSelect = this.el.querySelector('#counter');
        if (counterSelect && counterSelect.options.length === 2) {
            counterSelect.selectedIndex = 1;
            counterSelect.dispatchEvent(new Event('change'));
        }
        return this._super(...arguments);
    },

    _setCurrentDate() {
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];
        const dateField = this.el.querySelector('#date_field');
        if (dateField) {
            dateField.value = formattedDate;
        }
    },

    async _onCounterChange(ev) {
        const counterId = parseInt(ev.currentTarget.value);
        if (!counterId) return;

        try {
            const result = await rpc('/get/payment/amount/by/counter', { counter_id: counterId });
            if (result) {
                // Update cash in hand
                const totalCashField = this.el.querySelector('#total_cash_field');
                if (totalCashField) {
                    totalCashField.value = parseFloat(result.total_cash || 0).toFixed(2);
                }

                // Update transfer amount display
                const transferAmount = parseFloat(result.transfer_amount || 0);
                const transferAmountSpan = this.el.querySelector('#counter_transfer_amount');
                if (transferAmountSpan) {
                    transferAmountSpan.textContent = transferAmount.toFixed(2);
                }

                // Show rejected denomination warning if applicable
                if (result.has_rejected) {
                    this._showRejectedWarning(result.reject_reason);
                }

                // Show pending transfer modal if there are transfers
                if (result.transfer_list && result.transfer_list.length > 0) {
                    const transfer = result.transfer_list[0];
                    this._updateModalContent(transfer);
                    const modal = bootstrap.Modal.getOrCreateInstance(
                        this.el.querySelector('#cashTransferReviewModal')
                    );
                    if (modal) modal.show();
                }
            }
        } catch (err) {
            console.error('Error fetching payment amount:', err);
        }
    },

    _updateModalContent(transfer) {
        const setTextContent = (selector, value) => {
            const el = this.el.querySelector(selector);
            if (el) el.textContent = value;
        };
        
        setTextContent('#modal_total_transfer_cash', transfer.grand_total);
        setTextContent('#modal_from_user', transfer.from_user);
        setTextContent('#modal_from_counter', transfer.from_counter);
        setTextContent('#modal_date', transfer.date);
        setTextContent('#modal_amount', parseFloat(transfer.grand_total || 0).toFixed(2));
    },

    _showRejectedWarning(reason) {
        const form = this.el.querySelector('#cash_denomination_form');
        if (!form) return;
        
        // Remove existing warning if any
        const existingWarning = form.querySelector('.alert-warning');
        if (existingWarning) existingWarning.remove();
        
        const warningDiv = document.createElement('div');
        warningDiv.className = 'alert alert-warning alert-dismissible fade show';
        warningDiv.setAttribute('role', 'alert');
        warningDiv.innerHTML = `
            <strong>Previous submission was rejected!</strong>
            <p>Reason: ${reason || 'No reason provided'}</p>
            <p>Please review and resubmit your cash denomination.</p>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        form.insertBefore(warningDiv, form.firstChild);
    },

    _OpenTransferCashModal(ev) {
        ev.preventDefault();

        const counterSelect = this.el.querySelector('#counter');
        const selectedCounterId = counterSelect ? counterSelect.value : null;
        
        if (!selectedCounterId) {
            const selectModal = bootstrap.Modal.getOrCreateInstance(
                this.el.querySelector('#select-counter-modal')
            );
            if (selectModal) selectModal.show();
            return;
        }

        const totalCashField = this.el.querySelector('#total_cash_field');
        const cashInHand = parseFloat(totalCashField?.value) || 0;

        if (cashInHand <= 0) {
            const noCashModal = bootstrap.Modal.getOrCreateInstance(
                this.el.querySelector('#no-cash-modal-transfer')
            );
            if (noCashModal) noCashModal.show();
            return;
        }

        const transferModal = bootstrap.Modal.getOrCreateInstance(
            this.el.querySelector('#cash_transfer_modal')
        );
        if (transferModal) transferModal.show();
        
        this._fetchAllCounter(selectedCounterId);

        // Set hidden fields
        const fromCounter = this.el.querySelector('#from_selected_counter');
        const loggedUser = this.el.querySelector('#logged_user');
        const createdDate = this.el.querySelector('#created_date');
        const personField = this.el.querySelector('#person');
        const dateField = this.el.querySelector('#date_field');
        
        if (fromCounter) fromCounter.value = selectedCounterId;
        if (loggedUser && personField) loggedUser.value = personField.value;
        if (createdDate && dateField) createdDate.value = dateField.value;
    },

    async _fetchAllCounter(currentCounterId) {
        try {
            const result = await rpc('/get/all/counter');
            const counterSelect = this.el.querySelector('#to_all_locations');
            if (!counterSelect) return;
            
            counterSelect.innerHTML = '<option value="" disabled selected>Select Counter</option>';

            if (result?.locations?.length > 0) {
                result.locations.forEach((location) => {
                    if (location.id !== parseInt(currentCounterId)) {
                        const option = document.createElement('option');
                        option.value = location.id;
                        option.textContent = location.name;
                        counterSelect.appendChild(option);
                    }
                });
            } else {
                const option = document.createElement('option');
                option.disabled = true;
                option.textContent = 'No locations available';
                counterSelect.appendChild(option);
            }
        } catch (err) {
            console.error('Error fetching counters:', err);
        }
    },

    _onDenominationChange(ev) {
        const input = ev.currentTarget;
        const count = parseInt(input.value) || 0;
        const currency = parseInt(input.dataset.value) || 0;
        const total = count * currency;

        const row = input.closest('tr');
        const totalField = row?.querySelector('.total-field');
        if (totalField) {
            totalField.value = total.toFixed(2);
        }

        this._updateGrandTotal();
    },

    _updateGrandTotal() {
        let grandTotal = 0;
        this.el.querySelectorAll('.total-field').forEach((field) => {
            grandTotal += parseFloat(field.value) || 0;
        });
        const grandTotalField = this.el.querySelector('#grand_total');
        if (grandTotalField) {
            grandTotalField.value = grandTotal.toFixed(2);
        }
    },

    _onTransferDenominationChange(ev) {
        const input = ev.currentTarget;
        const count = parseInt(input.value) || 0;
        const currency = parseInt(input.dataset.value) || 0;
        const total = count * currency;

        const row = input.closest('tr');
        const totalField = row?.querySelector('.transfer-total-field');
        if (totalField) {
            totalField.value = total.toFixed(2);
        }

        this._updateTransferGrandTotal();
    },

    _updateTransferGrandTotal() {
        let grandTotal = 0;
        this.el.querySelectorAll('.transfer-total-field').forEach((field) => {
            grandTotal += parseFloat(field.value) || 0;
        });
        const transferGrandTotal = this.el.querySelector('#transfer_grand_total');
        if (transferGrandTotal) {
            transferGrandTotal.value = grandTotal.toFixed(2);
        }
    },

    _onTransferSubmit(ev) {
        ev.preventDefault();

        const grandTotalField = this.el.querySelector('#transfer_grand_total');
        const totalCashField = this.el.querySelector('#total_cash_field');
        const toLocationSelect = this.el.querySelector('#to_all_locations');

        const grandTotal = parseFloat(grandTotalField?.value) || 0;
        const cashInHand = parseFloat(totalCashField?.value) || 0;
        const toLocation = toLocationSelect?.value;

        if (!toLocation) {
            alert('Please select a destination counter.');
            return;
        }

        if (grandTotal === 0) {
            const noCountModal = bootstrap.Modal.getOrCreateInstance(
                this.el.querySelector('#no-count-modal')
            );
            if (noCountModal) noCountModal.show();
            return;
        }

        if (grandTotal > cashInHand) {
            const limitModal = bootstrap.Modal.getOrCreateInstance(
                this.el.querySelector('#transfer-limit-modal')
            );
            if (limitModal) limitModal.show();
            return;
        }

        this.el.querySelector('#cash_tranfer_form')?.submit();
    },

    _CashDenominationSubmit(ev) {
        ev.preventDefault();

        const counterSelect = this.el.querySelector('#counter');
        if (!counterSelect?.value) {
            const selectModal = bootstrap.Modal.getOrCreateInstance(
                this.el.querySelector('#select-counter-modal')
            );
            if (selectModal) selectModal.show();
            return;
        }

        const totalCashField = this.el.querySelector('#total_cash_field');
        const grandTotalField = this.el.querySelector('#grand_total');
        
        const cashInHand = parseFloat(totalCashField?.value) || 0;
        const grandTotal = parseFloat(grandTotalField?.value) || 0;

        if (grandTotal === 0) {
            const noCountModal = bootstrap.Modal.getOrCreateInstance(
                this.el.querySelector('#no-count-modal')
            );
            if (noCountModal) noCountModal.show();
            return;
        }

        if (grandTotal !== cashInHand) {
            const mismatchModal = bootstrap.Modal.getOrCreateInstance(
                this.el.querySelector('#mismatch-submit-modal')
            );
            if (mismatchModal) mismatchModal.show();

            const confirmBtn = this.el.querySelector('#confirm_mismatch_submit');
            if (confirmBtn) {
                confirmBtn.onclick = () => {
                    const remarkTextarea = this.el.querySelector('#mismatch_remark');
                    const remarkField = this.el.querySelector('#remark');
                    const remark = remarkTextarea?.value?.trim() || '';
                    const difference = grandTotal - cashInHand;
                    const fullRemark = remark
                        ? `${remark} (Difference: ${difference.toFixed(2)})`
                        : `Amount mismatch - Difference: ${difference.toFixed(2)}`;

                    if (remarkField) remarkField.value = fullRemark;
                    mismatchModal.hide();
                    this._submitDenomination();
                };
            }
            return;
        }

        this._submitDenomination();
    },

    _submitDenomination() {
        this.el.querySelector('#cash_denomination_form')?.submit();
    },

    _MismatchCashDenominationSubmit(ev) {
        ev.preventDefault();
        this._submitDenomination();
    }
});
