import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.CounterCashDenomination = publicWidget.Widget.extend({
    selector: '.cash_denomination_template',
    events: {
        'input .counts-input': '_onCountChange',
        'click #cash_transfer_btn': '_OpenTransferCashModal',
        'change #counter': '_onCounterChange',
        'click [data-bs-target="#transfer-details-modal"]': '_OpenTransferDetailsModal',
        'input .transfer-counts-input': '_onTransferCountChange',
        'submit #cash_denomination_form': '_CashDenominationSubmit',
        'submit #cash_tranfer_form': '_onTransferSubmit',
    },

    start: function () {
        this._super.apply(this, arguments);
        this._setCurrentDate();
        this.$('.counts-input').val('');
        this.$('.transfer-counts-input').val('');
        this.$('#grand_total').val('0.00');
        this.$('.total-field').val('');
        this.$('.transfer-total-field').val('');
        this.$('#transfer_grand_total').val('0.00');
        this.$('#total_cash_field').val('0.00');
        this._setupCounterUserLink();
        this._checkTransferSuccess();
        this._checkPendingTransfers();

    },

    _setCurrentDate: function () {
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];
        this.$('#date_field').val(formattedDate);
    },

    _onCounterChange: function (ev) {
        const counterId = parseInt(ev.currentTarget.value);
        if (!counterId) return;

        this._fetchPaymentAmountByCounter(counterId);
        this._checkPendingTransfers(counterId);
    },

    _setupCounterUserLink: function () {
        const self = this;

        document.querySelector('#counter')?.addEventListener('change', function (ev) {
            const counterId = ev.target.value;
            if (counterId) {
                self._fetchPaymentAmountByCounter(counterId);

                self._checkPendingTransfers(counterId);
            }
        });
    },


    _fetchPaymentAmountByCounter: function (counterId) {
        const self = this;
        rpc('/get/payment/amount/by/counter', { counter_id: counterId })
            .then(function (result) {
                if (result) {

                    self.$('#total_cash_field').val(parseFloat(result.total_cash || 0).toFixed(2));

                }
            })
            .catch(function (err) {
                console.error('Error fetching payment amount:', err);
            });
    },

    _onCountChange: function (ev) {
        const $input = $(ev.currentTarget);
        const count = parseInt($input.val()) || 0;
        const currency = parseInt($input.data('value')) || 0;
        const total = count * currency;

        const $row = $input.closest('tr');
        $row.find('.total-field').val(total.toFixed(2));

        this._updateGrandTotal();
    },

    _updateGrandTotal: function () {
        let grandTotal = 0;
        this.$('.total-field').each(function () {
            const val = parseFloat($(this).val()) || 0;
            grandTotal += val;
        });

        this.$('#grand_total').val(grandTotal.toFixed(2));
    },


    _CashDenominationSubmit: function (ev) {
        ev.preventDefault();

        const cashInHand = parseFloat(this.$('#total_cash_field').val()) || 0;
        const grandTotal = parseFloat(this.$('#grand_total').val()) || 0;

        if (grandTotal === 0) {
            $('#no-count-modal').modal('show');
            return;
        }

        if (grandTotal !== cashInHand) {

            $('#mismatch-submit-modal').modal('show');

            $('#confirm_mismatch_submit').off('click').on('click', () => {
                const remark = $('#mismatch_remark').val().trim();

                if (!remark) {
                    alert("Remark is required when submitting mismatch.");
                    return;
                }

                $('#remark').val(remark);

                $('#mismatch-submit-modal').modal('hide');
                this._submitDenomination();
            });

            return;
        }

        $('#success-modal').modal('show');
        $('#success-modal').one('hidden.bs.modal', () => {
            this._submitDenomination();
        });
    },

    _submitDenomination: function () {
        this.$('#cash_denomination_form')[0].submit();
    },

    _OpenTransferCashModal: function (ev) {
        ev.preventDefault();
        const selectedCounterId = this.$('#counter').val();
        const LoggedUser = this.$('#person').val();
        const CreatedDate = this.$('#date_field').val();
        const cashInHand = parseFloat(this.$('#total_cash_field').val()) || 0;
        if (cashInHand <= 0) {
            $('#no-cash-modal-transfer').modal('show');
            return;
        }
        else {
            $('#cash_transfer_modal').modal('show');
        }
        if (selectedCounterId) {
            this._fetchAllCounter();
        }

        $('#from_selected_counter').val(selectedCounterId);
        $('#logged_user').val(LoggedUser);
        $('#created_date').val(CreatedDate);
    },

    _fetchAllCounter: function () {
        rpc('/get/all/counter').then(function (result) {
            const counterSelect = self.$('#to_all_locations');
            counterSelect.empty();
            if (result && result.locations && result.locations.length > 0) {
                const locations = result.locations
                locations.forEach(location => {
                    counterSelect.append(`<option value="${location.id}">${location.name}</option>`);
                });

            } else {
                counterSelect.append('<option disabled selected>No location found</option>');
            }

        }).catch(function (err) {
            console.error('Error fetching petty users:', err);
        });
    },

    _onTransferCountChange: function (ev) {
        const $input = $(ev.currentTarget);
        const count = parseInt($input.val()) || 0;
        const currency = parseInt($input.data('value')) || 0;
        const total = count * currency;

        const $row = $input.closest('tr');
        $row.find('.transfer-total-field').val(total.toFixed(2));

        this._updateTransferGrandTotal();
    },
    _updateTransferGrandTotal: function () {
        let grandTotal = 0;
        this.$('.transfer-total-field').each(function () {
            const val = parseFloat($(this).val()) || 0;
            grandTotal += val;
        });
        this.$('#transfer_grand_total').val(grandTotal.toFixed(2));
    },

    _checkTransferSuccess: function () {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('transfer_success') === '1') {
            $('#transfer-success-modal').modal('show');

            const newUrl = window.location.pathname;
            window.history.replaceState({}, document.title, newUrl);
        }
    },


    _checkPendingTransfers: function (selectedCounterId) {
        const self = this;

        if (!selectedCounterId) return;


        rpc('/cash/transfer/pending').then(function (result) {
            if(result.user_flag == false){
                if (result.transfers && result.transfers.length > 0) {
                    const transfer = result.transfers.find(t => t.to_counter_id == parseInt(selectedCounterId));

                    if (!transfer) return;

                    $('#modal_from_user').text(transfer.from_user);
                    $('#modal_from_counter').text(transfer.from_counter);
                    $('#modal_date').text(transfer.date);
                    $('#modal_amount').text(transfer.grand_total.toFixed(2));
                    $('#cashTransferReviewModal').modal('show');

                    $('#accept_transfer').off('click').on('click', function () {
                        rpc('/cash/transfer/respond', {
                            transfer_id: transfer.id,
                            action: 'accept'
                        }).then((result) => {
                            $('#cashTransferReviewModal').modal('hide');

                            const addedAmount = parseFloat(result.added_amount || 0);
                            const currentCash = parseFloat($('#total_cash_field').val()) || 0;
                            $('#total_cash_field').val((currentCash + addedAmount).toFixed(2));

                            alert('Transfer Accepted!');
                        });
                    });


                    $('#reject_transfer').off('click').on('click', function () {
                        rpc('/cash/transfer/respond', {
                            transfer_id: transfer.id,
                            action: 'reject'
                        }).then(() => {
                            $('#cashTransferReviewModal').modal('hide');
                            alert('Transfer Rejected!');
                        });
                    });
                }
            }

        });
    },

    _OpenTransferDetailsModal: function (ev) {
        ev.preventDefault();
        const selectedCounterId = parseInt(this.$('#counter').val());
        if (!selectedCounterId) {
            alert("Please select a counter first!");
            return;
        }

        const self = this;

        rpc('/cash/transfer/details', { counter_id: selectedCounterId }).then(function (result) {
            if (!result.transfers) return;

            $('.outgoing').empty();
            $('.incoming').empty();

            const outgoingTransfers = result.transfers.filter(t => t.from_counter_id == selectedCounterId);
            outgoingTransfers.forEach(t => {
                const row = `<tr>
                <td>${t.to_counter_name}</td>
                <td>${parseFloat(t.grand_total).toFixed(2)}</td>
                <td>${t.date}</td>
                <td>${t.state}</td>
            </tr>`;
                $('.outgoing').append(row);
            });

            const incomingTransfers = result.transfers.filter(t => t.to_counter_id == selectedCounterId);
            incomingTransfers.forEach(t => {
                const row = `<tr>
                <td>${t.from_counter}</td>
                <td>${t.from_user}</td>
                <td>${parseFloat(t.grand_total).toFixed(2)}</td>
                <td>${t.date}</td>
                <td>${t.state}</td>
            </tr>`;
                $('.incoming').append(row);
            });

            $('#transfer-details-modal').modal('show');
        });
    },
    _onTransferSubmit: function (ev) {
        ev.preventDefault();

        const grandTotal = parseFloat(this.$('#transfer_grand_total').val()) || 0;
        const cashInHand = parseFloat(this.$('#total_cash_field').val()) || 0;

        if (grandTotal > cashInHand) {
            $('#transfer-limit-modal').modal('show');   
            return;                                     
        }

        this.$('#cash_tranfer_form')[0].submit();
    },


});