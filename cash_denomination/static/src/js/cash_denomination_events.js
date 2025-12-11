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

    start: function () {
        this._super.apply(this, arguments);
        this._setCurrentDate();
    },

    _setCurrentDate: function () {
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];
        this.$('#date_field').val(formattedDate);
    },

    _onCounterChange: function (ev) {
        const counterId = parseInt(ev.currentTarget.value);
        if (!counterId) return;
        const self = this;
        rpc('/get/payment/amount/by/counter', { counter_id: counterId })
            .then(function (result) {
                if (result) {
                    console.log("result", result);
                    self.$('#total_cash_field').val(parseFloat(result.total_cash || 0).toFixed(2));
                    let transferCash = parseFloat(result.transfer_amount || 0);
                    const transfer = result.transfer_list[0];
                    $('#counter_transfer_amount').text(transferCash);
                    console.log("transfer", transfer);
                    if (transfer) {
                        const transfer_id = transfer.id
                        console.log("transferCash", transfer);
                        console.log("transfer.from_counter", transfer.from_counter);
                        console.log("transfer.date", transfer.date);
                        console.log("transfer.grand_total", transfer.grand_total);
                        $('#modal_total_transfer_cash').text(transfer.grand_total);
                        $('#modal_from_user').text(transfer.from_user);
                        $('#modal_from_counter').text(transfer.from_counter);
                        $('#modal_date').text(transfer.date);
                        $('#modal_amount').text(parseFloat(transfer.grand_total || 0).toFixed(2));
                        $('#cashTransferReviewModal').modal('show');

                        $('#accept_transfer').off('click').on('click', function () {
                            $('#cashTransferReviewModal').modal('hide');
                            rpc('/cash/transfer/respond', {
                                transfer_id: transfer_id,
                                action: 'accept'
                            }).then((result) => {

                                const addedAmount = parseFloat(result.added_amount || 0);
                                const currentCash = parseFloat($('#total_cash_field').val()) || 0;
                                $('#total_cash_field').val((currentCash + addedAmount).toFixed(2));
                            });
                        });

                        $('#reject_transfer').off('click').on('click', function () {

                            $('#cashTransferReviewModal').modal('hide');
                            rpc('/cash/transfer/respond', {
                                transfer_id: transfer.id,
                                action: 'reject'
                            }).then(() => {
                                $('#cashTransferReviewModal').modal('hide');
                            });
                        });
                    }
                }

            })
            .catch(function (err) {
                console.error('Error fetching payment amount:', err);
            });
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

    _onDenominationChange: function (ev) {
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


    _onTransferDenominationChange: function (ev) {
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

    _onTransferSubmit: function (ev) {
        ev.preventDefault();

        const grandTotal = parseFloat(this.$('#transfer_grand_total').val()) || 0;
        const cashInHand = parseFloat(this.$('#total_cash_field').val()) || 0;

        if (grandTotal === 0) {
            $('#no-count-modal').modal('show');
            return;
        }
        if (grandTotal > cashInHand) {
            $('#transfer-limit-modal').modal('show');
            return;
        }

        this.$('#cash_tranfer_form')[0].submit();
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

                $('#remark').val(remark);

                $('#mismatch-submit-modal').modal('hide');
                this._submitDenomination();
            });

            return;
        }
        this._submitDenomination();

    },
    _submitDenomination: function () {

        this.$('#cash_denomination_form')[0].submit();
    },

    _MismatchCashDenominationSubmit: function (ev) {
        ev.preventDefault();
        this._submitDenomination();
    }

});