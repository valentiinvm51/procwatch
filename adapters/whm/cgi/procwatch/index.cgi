#!/usr/local/cpanel/3rdparty/bin/perl
#WHMADDON:procwatch:ProcWatch:procwatch.png
#ACLS:all

use strict;
use warnings;

use Cpanel::Template ();

run() unless caller();

sub run {
    print "Content-type: text/html\r\n\r\n";

    Cpanel::Template::process_template(
        'whostmgr',
        {
            'template_file' => 'procwatch/index.tmpl',
            'print'         => 1,
        }
    );

    exit;
}
