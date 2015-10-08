#!/bin/env python2
# -*- coding: utf-8 -*-
"""
Recursively import images from directories in Wordpress, as Exposed galleries.
"""
import MySQLdb
import os
import re
import shutil
from datetime import date
import time
import argparse

class Directory2Gallery(object):
    """ main (and only) class """
    parameters = None
    cnx = None
    cur = None

    def _get_wp_parameters(self, wp_path):
        """ Retrieve wordpress parameters """
        with open("%s/wp-config.php" % wp_path) as wp_config_file:
            wp_config = {x[0]: x[1] for x in
                         [line.split("'")[1::2]
                          for line in wp_config_file.readlines()
                          if line.startswith("define(")]
                         if len(x) > 1}
        self.parameters = {'wp-path': wp_path,
                           'db_host': wp_config['DB_HOST'],
                           'db': wp_config['DB_NAME'],
                           'db_username': wp_config['DB_USER'],
                           'db_password': wp_config['DB_PASSWORD']}

    def _connect_db(self):
        """ connect to the database """
        self.cnx = MySQLdb.connect(host=self.parameters['db_host'],
                                   user=self.parameters['db_username'],
                                   passwd=self.parameters['db_password'],
                                   db=self.parameters['db'])
        self.cur = self.cnx.cursor()
        self.cur.execute("SELECT option_value FROM wp_options WHERE option_name LIKE 'siteurl';")
        self.parameters['url'] = self.cur.fetchone()[0]

    def _insert_post(self, data):
        return self._insert_sqlinto('wp_posts', data)

    def _insert_post_meta(self, data):
        return self._insert_sqlinto('wp_postmeta', data)

    def _insert_sqlinto(self, table, data):
        data_sql = 'INSERT INTO %s SET %s;' % (table,
                                               ', '.join(["%s=%s" % (k, v)\
                                                          for k, v in data.iteritems()]))
        self.cur.execute(data_sql)
        self.cnx.commit()
        return self.cur.lastrowid

    def attach_image(self, srcdir, image):
        """ Attach image """
        today = date.today()
        wp_upload = "%s/%s" % (today.year, today.month)
        wp_image_path = "%s/wp-content/uploads/%s" % (self.parameters['wp-path'], wp_upload)
        if not os.path.isdir(wp_image_path):
            os.mkdir(wp_image_path)
        def find_unique_name(wp_image_name):
            """ Find a unique name by iteratively adding suffixes """
            def is_name_unique(name):
                """ Check if a given file name is unique """
                return not os.path.isfile(name)
            count = 0
            while not is_name_unique("%s/%s" % (wp_image_path, wp_image_name)):
                wp_image_name = "%s_%s.%s" % (wp_image_name[:wp_image_name.rindex('.')],
                                              count,
                                              wp_image_name[wp_image_name.rindex('.')+1:])
                count += 1
            return wp_image_name
        wp_image_name = find_unique_name(image)
        shutil.copyfile("%s/%s" % (srcdir, image), "%s/%s" % (wp_image_path, wp_image_name))

        mysql_date = time.strftime('"%Y-%m-%d %H:%M:%S"')
        guid = '%s/wp-content/uploads/%s/%s' % (self.parameters['url'], wp_upload, wp_image_name)
        image_data = {'post_author': 0,
                      'post_date': mysql_date,
                      'post_date_gmt': mysql_date,
                      'post_status': '"inherit"',
                      'comment_status': '"open"',
                      'ping_status': '"closed"',
                      'post_name': '"%s"' % wp_image_name,
                      'post_modified': mysql_date,
                      'post_parent': 0,
                      'guid': '"%s"' % guid,
                      'menu_order': 0,
                      'post_type': '"attachment"',
                      'post_mime_type': '"image/jpeg"',
                      'comment_count': 0,
                      'post_content': '""',
                      'post_title': '"%s"' % wp_image_name,
                      'post_excerpt': '""',
                      'to_ping': '""',
                      'pinged': '""',
                      'post_content_filtered': '""'}
        post_id = self._insert_post(image_data)
        image_meta = {'post_id': post_id,
                      'meta_key': '"_wp_attached_file"',
                      'meta_value': '"%s/%s"'%(wp_upload, wp_image_name)}
        self._insert_post_meta(image_meta)
        return post_id

    def create_gallery(self, title, image_ids):
        """ Create the Exposed gallery """
        mysql_date = time.strftime('"%Y-%m-%d %H:%M:%S"')
        gallery_data = {'post_author': 1,
                        'post_date': mysql_date,
                        'post_date_gmt': mysql_date,
                        'post_status': '"publish"',
                        'comment_status': '"closed"',
                        'ping_status': '"closed"',
                        'post_name': '"%s"' % title,
                        'post_modified': mysql_date,
                        'post_parent': 0,
                        'guid': '""',
                        'menu_order': 0,
                        'post_type': '"gallery"',
                        'comment_count': 0,
                        'post_mime_type': '""',
                        'post_content': '""',
                        'post_title': '"%s"' % title,
                        'post_excerpt': '""',
                        'to_ping': '""',
                        'pinged': '""',
                        'post_content_filtered': '""'}
        post_id = self._insert_post(gallery_data)
        # insert guid
        guid = '%s/?post_type=gallery&#038;p=%s' % (self.parameters['url'], post_id)
        sql = "UPDATE wp_posts SET guid='%s' WHERE ID = %s" % (guid, post_id)
        self.cur.execute(sql)
        self.cnx.commit()
        # Generate gallery meta, ugly but it works :-)
        def gen_metadata(image_ids):
            """ Generate the strange metadata describing Exposed galleries. """
            prefix = 'a:2:{s:4:"meta";a:%s:{' % len(image_ids)
            array = []
            for i in range(len(image_ids)):
                array.append('i:%s;a:3:{s:5:"title";s:0:"";s:7:"caption";s:0:"";s:3:"url";s:0:"";}' % i)
            first = ''.join(array)
            middle = '}s:6:"images";a:%s:{' %  len(image_ids)
            array = []
            for i in range(len(image_ids)):
                array.append('i:%s;s:%s:"%s";' % (i, len(str(image_ids[i])), image_ids[i]))
            second = ''.join(array)
            suffix = '}}'
            to_return = "%s%s%s%s%s" % (prefix, first, middle, second, suffix)
            return to_return

        self._insert_post_meta({'post_id': post_id,
                                'meta_key': '"_st_gallery"',
                                'meta_value': "'%s'" % gen_metadata(image_ids)})
        return post_id

    def __init__(self, wp_directory):
        self._get_wp_parameters(wp_directory)
        self._connect_db()

    def add_galleries_from(self, directory):
        """ Recursively add directories as galleries """
        all_files = os.listdir(directory)
        images = [f for f in all_files if re.match(r'[^_].*\.jpg$', f)]
        image_ids = [self.attach_image(directory, i) for i in images]
        if len(image_ids) > 0:
            post_id = self.create_gallery(os.path.basename(directory), image_ids)
            print "Directory %s (%s files) -> gallery (post %s), contains %s images (from posts %s)" % \
                (os.path.basename(directory), len(all_files), post_id, len(image_ids), \
                 ', '.join(str(l) for l in image_ids))
        else:
            print "No image imported from %s" % directory
        [self.add_galleries_from("%s/%s" % (directory, d)) for d in os.listdir(directory)
         if os.path.isdir("%s/%s" % (directory, d))]

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=\
        "Recursively import images from directories in Wordpress, as Exposed galleryies.")
    parser.add_argument('--wordpress-directory', '-w',
                        dest='wordpress_directory',
                        required=True,
                        help="Path to the wordpress installation (where is wp-config.php).")
    parser.add_argument('--directory', '-d',
                        dest='directory',
                        required=True,
                        help="Path to the local directory to import galleries from.")
    args = parser.parse_args()
    Directory2Gallery(args.wordpress_directory).add_galleries_from(args.directory)
