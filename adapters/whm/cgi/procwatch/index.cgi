#!/usr/local/cpanel/3rdparty/bin/perl
#WHMADDON:procwatch:ProcWatch:procwatch.png
#ACLS:all

use strict;
use warnings;

use Cpanel::Template ();
use CGI ();

run() unless caller();

sub _read_version {
    my $path = '/usr/local/cpanel/whostmgr/docroot/cgi/procwatch/VERSION';
    if ( open( my $fh, '<', $path ) ) {
        my $v = <$fh>;
        close $fh;
        $v ||= '';
        $v =~ s/\s+\z//;
        return $v if $v ne '';
    }
    return 'dev';
}

sub run {
    my $q      = CGI->new();
    my $action = $q->param('action') || '';

    if ( $action eq 'metrics' ) {
        print "Content-type: application/json\r\n\r\n";
        # metrics.cgi now prints JSON only (no headers).
        my $out = `/usr/local/cpanel/whostmgr/docroot/cgi/procwatch/metrics.cgi`;
        print $out;
        exit;
    }

    print "Content-type: text/html\r\n\r\n";

    my $version = _read_version();

    Cpanel::Template::process_template(
        'whostmgr',
        {
            'template_file' => 'procwatch/index.tmpl',
            'print'         => 1,
            'template_args' => {
                'procwatch_version' => $version,
            },
        }
    );

    exit;
}
