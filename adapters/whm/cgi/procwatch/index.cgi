#!/usr/local/cpanel/3rdparty/bin/perl
#WHMADDON:procwatch:ProcWatch:procwatch.png
#ACLS:all

use strict;
use warnings;

use Cpanel::Template ();
use CGI ();

run() unless caller();

sub run {
    my $q = CGI->new();
    my $action = $q->param('action') || '';

    if ( $action eq 'metrics' ) {
        print "Content-type: application/json\r\n\r\n";
        # Call the bash collector and stream its output
        system('/usr/local/cpanel/whostmgr/docroot/cgi/procwatch/metrics.cgi');
        exit;
    }

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
