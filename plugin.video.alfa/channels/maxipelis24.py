# -*- coding: utf-8 -*-

import re
import urlparse
import urllib

from core import tmdb
from core import servertools
from core import httptools
from core import scrapertools
from core.item import Item
from platformcode import config, logger
from channelselector import get_thumb

host = "https://maxipelis24.tv"


def mainlist(item):
    logger.info()
    itemlist = []

    itemlist.append(Item(channel=item.channel, title="Peliculas",
                         action="movies", url=host, page=0, thumbnail=get_thumb('movies', auto=True)))
    itemlist.append(Item(channel=item.channel, action="category", title="Año de Estreno",
                         url=host, cat='year', page=0, thumbnail=get_thumb('year', auto=True)))
    itemlist.append(Item(channel=item.channel, action="category", title="Géneros",
                         url=host, cat='genre', page=0, thumbnail=get_thumb('genres', auto=True)))
    itemlist.append(Item(channel=item.channel, action="category", title="Calidad",
                         url=host, cat='quality', page=0, thumbnail=get_thumb("quality", auto=True)))
    itemlist.append(Item(channel=item.channel, title="Buscar", action="search",
                         url=host + "?s=", page=0, thumbnail=get_thumb("search", auto=True)))

    return itemlist


def search(item, texto):
    logger.info()
    texto = texto.replace(" ", "+")
    item.url = host + "?s=" + texto
    if texto != '':
        return movies(item)


def category(item):
    logger.info()
    itemlist = []
    data = httptools.downloadpage(item.url).data
    data = re.sub(r"\n|\r|\t|\s{2}|&nbsp;", "", data)
    if item.cat == 'genre':
        data = scrapertools.find_single_match(
            data, '<h3>Géneros <span class="icon-sort">.*?</ul>')
        patron = '<li class="cat-item cat-item.*?<a href="([^"]+)" >([^<]+)<'
    elif item.cat == 'year':
        data = scrapertools.find_single_match(
            data, '<h3>Año de estreno.*?</div>')
        patron = 'li><a href="([^"]+)">([^<]+).*?<'
    elif item.cat == 'quality':
        data = scrapertools.find_single_match(data, '<h3>Calidad.*?</div>')
        patron = 'li><a href="([^"]+)">([^<]+)<'
    matches = re.compile(patron, re.DOTALL).findall(data)
    for scrapedurl, scrapedtitle in matches:
        itemlist.append(Item(channel=item.channel, action='movies',
                             title=scrapedtitle, url=scrapedurl, type='cat', page=0))
    return itemlist


def movies(item):
    logger.info()
    itemlist = []
    data = httptools.downloadpage(item.url).data
    data = re.sub(r"\n|\r|\t|\s{2}|&nbsp;", "", data)
    patron = '<div id="mt.+?href="([^"]+)".+?'
    patron += '<img src="([^"]+)" alt="([^"]+)".+?'
    patron += '<span class="ttx">([^<]+).*?'
    patron += 'class="year">([^<]+).+?class="calidad2">([^<]+)<'
    matches = re.compile(patron, re.DOTALL).findall(data)
    for scrapedurl, img, scrapedtitle, resto,  year, quality in matches[item.page:item.page + 30]:
        scrapedtitle = re.sub(r' \((\d+)\)', '', scrapedtitle)
        plot = scrapertools.htmlclean(resto).strip()
        title = ' %s [COLOR red][%s][/COLOR]' % (scrapedtitle, quality)
        itemlist.append(Item(channel=item.channel,
                             title=title,
                             url=scrapedurl,
                             action="findvideos",
                             plot=plot,
                             thumbnail=img,
                             contentTitle=scrapedtitle,
                             contentType="movie",
                             quality=quality,
                             infoLabels={'year': year}))
    tmdb.set_infoLabels_itemlist(itemlist, seekTmdb=True)
    # Paginacion
    if item.page + 30 < len(matches):
        itemlist.append(item.clone(page=item.page + 30, title=">> Siguiente"))
    else:
        next_page = scrapertools.find_single_match(
            data, 'class="respo_pag"><div class="pag.*?<a href="([^"]+)" >Siguiente</a><')
        if next_page:
            itemlist.append(item.clone(
                url=next_page, page=0, title=">> Siguiente"))
    return itemlist


def findvideos(item):
    logger.info()
    itemlist = []
    data = httptools.downloadpage(item.url).data
    data = re.sub(r"\n|\r|\t|\s{2}|&nbsp;", "", data)
    patron = '<div id="div.*?<div class="movieplay".*?(?:iframe.*?src|IFRAME SRC)="([^&]+)&'
    matches = re.compile(patron, re.DOTALL).findall(data)
    for link in matches:
        if 'maxipelis24.tv/hideload/?' in link:
            if 'id=' in link:
                id_type = 'id'
                ir_type = 'ir'
            elif 'ud=' in link:
                id_type = 'ud'
                ir_type = 'ur'
            elif 'od=' in link:
                id_type = 'od'
                ir_type = 'or'
            elif 'ad=' in link:
                id_type = 'ad'
                ir_type = 'ar'
            elif 'ed=' in link:
                id_type = 'ed'
                ir_type = 'er'
            id = scrapertools.find_single_match(link, '%s=(.*)' % id_type)
            base_link = scrapertools.find_single_match(
                link, '(.*?)%s=' % id_type)
            ir = id[::-1]
            referer = base_link+'%s=%s&/' % (id_type, ir)
            video_data = httptools.downloadpage('%s%s=%s' % (base_link, ir_type, ir), headers={'Referer': referer},
                                                follow_redirects=False)
            url = video_data.headers['location']
            title = '%s'
            new_item = Item(channel=item.channel, title=title, url=url,
                            action='play', language='', infoLabels=item.infoLabels)
            itemlist.append(new_item)
        else:
            patron = '<div id="div.*?<div class="movieplay".*?(?:iframe.*?src|IFRAME SRC)="([^"]+)"'
            matches = re.compile(patron, re.DOTALL).findall(data)
            for link in matches:
                url = link
                title = '%s'
                new_item = Item(channel=item.channel, title=title, url=url,
                                action='play', language='', infoLabels=item.infoLabels)
                itemlist.append(new_item)
    itemlist = servertools.get_servers_itemlist(
        itemlist, lambda x: x.title % x.server.capitalize())
    if itemlist:
        if config.get_videolibrary_support():
            itemlist.append(Item(channel=item.channel, action=""))
            itemlist.append(Item(channel=item.channel, title="Añadir a la videoteca", text_color="green",
                                 action="add_pelicula_to_library", url=item.url, thumbnail=item.thumbnail,
                                 contentTitle=item.contentTitle
                                 ))
    return itemlist
