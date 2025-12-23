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

    _openRejectModal: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        $('#rejectReasonModal').modal('show');
    },

    _rejectTransferAmount: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();

        const ctNumber = $('#ct_number').text().trim();
        const reason = $('.reject-reason').val().trim();

        rpc('/cash/transfer/amount/reject', {
            transfer_number: ctNumber,
            reject_reason: reason,
        }).then((result) => {
            $('#rejectReasonModal').modal('hide');
            window.location.href = '/pending/cash/transfer';
        });
    },


    _onCounterChange: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const counterId = parseInt(ev.currentTarget.value);
        rpc('/check/cash/transfer/by/counter', {
            counter_id: counterId,
        }).then((result) => {
            $('#ct_date').text('');
            $('#ct_number').text('');
            $('#ct_from_user').text('');
            $('#ct_from_counter').text('');
            $('#ct_to_counter').text('');
            $('#denomination_tbody').empty();
            $('#denomination_total').text('0.00');
            const transfer_data = result.transfer_list
            transfer_data.forEach(data => {
                $('#ct_date').text(data.date);
                $('#ct_number').text(data.name);
                $('#ct_from_user').text(data.from_user);
                $('#ct_from_counter').text(data.from_counter);
                $('#ct_to_counter').text(data.to_counter);
                const denominations = data.denomination_list || [];

                const $tbody = $('#denomination_tbody');
                const $total = $('#denomination_total');

                $tbody.empty();
                let grandTotal = 0;

                denominations.forEach(den => {
                    grandTotal += den.total;

                    $tbody.append(`
                        <tr>
                            <td>INR</td>
                            <td>${den.amount}</td>
                            <td>${den.counts}</td>
                            <td>${den.total.toFixed(2)}</td>
                        </tr>
                    `);
                });

                $total.text(grandTotal.toFixed(2));
            });
        });
    },

    _acceptTransferAmount: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const ctNumber = $('#ct_number').text().trim();
        if (ctNumber) {
            rpc('/cash/transfer/amount/accept', {
                counter_name: ctNumber,
            }).then((result) => {
                window.location.href = '/cash/transfer/accepted';
            });
        }
    },

});
