#!/usr/local/cpanel/3rdparty/bin/perl
#WHMADDON:procwatch:ProcWatch:procwatch.png
#ACLS:all

use strict;
use warnings;

use Cpanel::Template ();
use CGI ();

run() unless caller();

sub read_version {
    my $path = '/usr/local/cpanel/whostmgr/docroot/cgi/procwatch/VERSION';

    if ( open my $fh, '<', $path ) {
        my $v = <$fh>;
        close $fh;
        $v ||= '';
        $v =~ s/\s+$//;
        return $v if $v ne '';
    }

    return 'dev';
}

sub run {
    my $q      = CGI->new();
    my $action = $q->param('action') || '';

    # JSON endpoint
    if ( $action eq 'metrics' ) {
        print "Content-type: application/json\r\n\r\n";
        print `/usr/local/cpanel/whostmgr/docroot/cgi/procwatch/metrics.cgi`;
        exit;
    }

    # HTML UI
    print "Content-type: text/html\r\n\r\n";

    my $version = read_version();

    Cpanel::Template::process_template(
        'whostmgr',
        {
            template_file       => 'procwatch/index.tmpl',
            print               => 1,
            procwatch_version   => $version
        }
    );
}
