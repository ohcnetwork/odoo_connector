import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.TransferView = publicWidget.Widget.extend({
    selector: '.cash_transfer_register_template',
    events: {
        'click .view-transfer-btn': '_toggleTransferBox',
        'click .close-transfer-btn': '_closeTransferBox',
    },

    _toggleTransferBox: function (ev) {
        ev.stopPropagation();

        const $button = $(ev.currentTarget);
        const $box = $button.siblings('.transfer-box');
        const hasLines = $button.data("has-lines");

        const $msg = $box.find('.no-transfer-lines');
        const $table = $box.find('.transfer-table');

        // Hide all other open boxes
        $(".transfer-box").not($box).slideUp();

        // Show only message or table
        if (!hasLines) {
            $table.hide();
            $msg.show();
        } else {
            $msg.hide();
            $table.show();
        }

        // Toggle the selected box
        $box.slideToggle();

        // Close when clicking outside
        $(document).off('click.transferOutside').on('click.transferOutside', function (e) {
            if (!$box.is(e.target) && $box.has(e.target).length === 0) {
                $box.slideUp();
                $(document).off('click.transferOutside');
            }
        });
    },

    _closeTransferBox: function (ev) {
        ev.stopPropagation();
        const $box = $(ev.currentTarget).closest('.transfer-box');
        $box.slideUp();
        $(document).off('click.transferOutside');
    },
});
