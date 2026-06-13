package org.apollo.jagcached;

import java.io.File;
import java.io.IOException;
import java.net.BindException;
import java.net.InetSocketAddress;
import java.net.SocketAddress;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.rs2.Constants;
import org.apollo.game.session.ApolloHandler;
import org.apollo.net.HttpChannelInitializer;
import org.apollo.net.JagGrabChannelInitializer;
import org.apollo.net.ServiceChannelInitializer;

import io.netty.bootstrap.ServerBootstrap;
import io.netty.channel.ChannelInitializer;
import io.netty.channel.EventLoopGroup;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioServerSocketChannel;

/**
 * The core class of the file server.
 * @author Graham
 */
public final class FileServer {
	
	/**
	 * The {@link ServerBootstrap} for the HTTP listener.
	 */
	private ServerBootstrap httpBootstrap;

	/**
	 * The {@link ServerBootstrap} for the JAGGRAB listener.
	 */
	private ServerBootstrap jaggrabBootstrap;

	/**
	 * The event loop group.
	 */
	private final EventLoopGroup loopGroup = new NioEventLoopGroup();

	/**
	 * The {@link ServerBootstrap} for the service listener.
	 */
	private final ServerBootstrap serviceBootstrap = new ServerBootstrap();
	
	
	/**
	 * The logger for this class.
	 */
	private static final Logger logger = Logger.getLogger(FileServer.class.getName());

	
	/**
	 * The request worker pool.
	 */
	private RequestWorkerPool pool;


	/**
	 * Starts the file server.
	 * @throws Exception if an error occurs.
	 */
	public SocketAddress service = bindAddress(Constants.GAME_BIND_HOST, gamePort());

	public void start() throws Exception {
		if (!new File(Constants.FILE_SYSTEM_DIR).exists())
		{
			System.out.println("Working Directory = " + System.getProperty("user.dir"));
			System.out.println("************************************");
			System.out.println("************************************");
			System.out.println("************************************");
			System.out.println("WARNING: I could not find the data/cache folder. You are LIKELY running this in the wrong directory!");
			System.out.println("In IntelliJ, fix it by clicking \"GameEngine\" > Edit Configurations at the top of your screen");
			System.out.println("Then changing the \"Working Directory\" to be in \"2006Scape/2006Scape Server\", instead of just \"2006Scape\"");
			System.out.println("************************************");
			System.out.println("************************************");
			System.out.println("************************************");
			System.exit(1);
		}

		if(Constants.FILE_SERVER) {
			httpBootstrap = new ServerBootstrap();
			jaggrabBootstrap = new ServerBootstrap();
			pool = new RequestWorkerPool();
			logger.info("Starting workers...");
			pool.start();
		}
		logger.info("Starting services...");
		
		init();
		List<SocketAddress> serviceAddresses = bindAddresses(Constants.GAME_BIND_HOSTS, Constants.GAME_BIND_HOST, gamePort());
		List<SocketAddress> httpAddresses = bindAddresses(Constants.HTTP_BIND_HOSTS, Constants.HTTP_BIND_HOST, Constants.HTTP_PORT);
		List<SocketAddress> jaggrabAddresses = bindAddresses(Constants.JAGGRAB_BIND_HOSTS, Constants.JAGGRAB_BIND_HOST, Constants.JAGGRAB_PORT);
		service = serviceAddresses.get(0);

		bind(serviceAddresses, httpAddresses, jaggrabAddresses);
		
		logger.info("Ready for connections.");
	}

	/**
	 * Initialises the server.
	 *
	 * @throws Exception If an error occurs.
	 */
	public void init() throws Exception {
		
		serviceBootstrap.group(loopGroup);
		if(Constants.FILE_SERVER) {
			httpBootstrap.group(loopGroup);
			jaggrabBootstrap.group(loopGroup);		
		}
		ApolloHandler handler = new ApolloHandler();

		ChannelInitializer<SocketChannel> service = new ServiceChannelInitializer(handler);
		serviceBootstrap.channel(NioServerSocketChannel.class);
		serviceBootstrap.childHandler(service);

		if(!Constants.FILE_SERVER)
			return;
		ChannelInitializer<SocketChannel> http = new HttpChannelInitializer(handler);
		httpBootstrap.channel(NioServerSocketChannel.class);
		httpBootstrap.childHandler(http);

		ChannelInitializer<SocketChannel> jaggrab = new JagGrabChannelInitializer(handler);
		jaggrabBootstrap.channel(NioServerSocketChannel.class);
		jaggrabBootstrap.childHandler(jaggrab);
	}
	
	/**
	 * Binds the server to the specified address.
	 *
	 * @param service The service address to bind to.
	 * @param http The HTTP address to bind to.
	 * @param jaggrab The JAGGRAB address to bind to.
	 * @throws BindException If the ServerBootstrap fails to bind to the SocketAddress.
	 */
	public void bind(SocketAddress service, SocketAddress http, SocketAddress jaggrab) throws IOException {
		List<SocketAddress> serviceAddresses = new ArrayList<SocketAddress>();
		serviceAddresses.add(service);
		List<SocketAddress> httpAddresses = new ArrayList<SocketAddress>();
		httpAddresses.add(http);
		List<SocketAddress> jaggrabAddresses = new ArrayList<SocketAddress>();
		jaggrabAddresses.add(jaggrab);
		bind(serviceAddresses, httpAddresses, jaggrabAddresses);
	}

	/**
	 * Binds the server to one or more configured addresses.
	 *
	 * @param serviceAddresses The service addresses to bind to.
	 * @param httpAddresses The HTTP addresses to bind to.
	 * @param jaggrabAddresses The JAGGRAB addresses to bind to.
	 * @throws BindException If a ServerBootstrap fails to bind to any required SocketAddress.
	 */
	public void bind(List<SocketAddress> serviceAddresses, List<SocketAddress> httpAddresses,
			List<SocketAddress> jaggrabAddresses) throws IOException {
		bindAll(serviceBootstrap, serviceAddresses, "service");
		if (Constants.FILE_SERVER) {
			try {
				bindAll(httpBootstrap, httpAddresses, "HTTP");
			} catch (IOException cause) {
				if (httpBindFailureIsFatal()) {
					throw new IOException("Unable to bind the HTTP cache listener in external-player mode.", cause);
				}
				logger.log(Level.WARNING, "Unable to bind to HTTP - JAGGRAB will be used as a fallback.", cause);
			}
	
			bindAll(jaggrabBootstrap, jaggrabAddresses, "JAGGRAB");
		}
		logger.info("Ready for connections.");
	}

	static boolean httpBindFailureIsFatal() {
		return Constants.EXTERNAL_PLAYERS_ENABLED;
	}

	private void bindAll(ServerBootstrap bootstrap, List<SocketAddress> addresses, String label) throws IOException {
		for (SocketAddress address : addresses) {
			logger.fine("Binding " + label + " listener to address: " + address + "...");
			bind(bootstrap, address);
		}
	}
	
	/**
	 * Attempts to bind the specified ServerBootstrap to the specified SocketAddress.
	 *
	 * @param bootstrap The ServerBootstrap.
	 * @param address The SocketAddress.
	 * @throws IOException If the ServerBootstrap fails to bind to the SocketAddress.
	 */
	private void bind(ServerBootstrap bootstrap, SocketAddress address) throws IOException {
		try {
			bootstrap.bind(address).sync();
		} catch (Exception cause) {
			throw new IOException("Failed to bind to " + address, cause);
		}
	}

	static SocketAddress bindAddress(String host, int port) {
		if (host == null || host.trim().isEmpty() || "*".equals(host.trim())) {
			return new InetSocketAddress(port);
		}
		return new InetSocketAddress(host.trim(), port);
	}

	static List<SocketAddress> bindAddresses(String[] hosts, String fallbackHost, int port) {
		LinkedHashSet<String> uniqueHosts = new LinkedHashSet<String>();
		if (hosts != null) {
			for (String host : hosts) {
				if (host != null && !host.trim().isEmpty()) {
					uniqueHosts.add(host.trim());
				}
			}
		}
		if (uniqueHosts.isEmpty()) {
			uniqueHosts.add(fallbackHost);
		}
		ArrayList<SocketAddress> addresses = new ArrayList<SocketAddress>();
		for (String host : uniqueHosts) {
			addresses.add(bindAddress(host, port));
		}
		return addresses;
	}

	static int gamePort() {
		return Constants.GAME_PORT > 0 ? Constants.GAME_PORT : ((Constants.WORLD == 1) ? 43594 : 43596 + Constants.WORLD);
	}

}
